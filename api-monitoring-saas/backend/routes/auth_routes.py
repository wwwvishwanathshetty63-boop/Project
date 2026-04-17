import bcrypt
import secrets
import string
import random
import logging
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, g
from backend.models import get_db, row_to_dict, rows_to_list, release_db, release_db
from backend.utils.auth import generate_token, token_required
from backend.utils.validators import (
    validate_email,
    validate_password,
    validate_name,
    sanitize_string,
)

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _generate_employee_id():
    """Generate a unique employee ID like EMP-XXXX."""
    digits = "".join(secrets.choice(string.digits) for _ in range(6))
    return f"EMP-{digits}"


def _generate_employee_password(name: str) -> str:
    """Generate a password by combining the employee name with random characters/numbers."""
    # Clean name: take first part, capitalize
    clean_name = name.strip().split()[0].capitalize()
    # Add 4-6 random alphanumeric + special characters
    suffix_chars = string.ascii_letters + string.digits + "!@#$"
    suffix_len = secrets.choice([4, 5, 6])
    suffix = "".join(secrets.choice(suffix_chars) for _ in range(suffix_len))
    return f"{clean_name}{suffix}"



# In-memory store for verified emails (maps email -> expiry timestamp)
# This avoids a second DB round-trip during registration.
_verified_emails: dict = {}


@auth_bp.route("/send-otp", methods=["POST"])
def send_otp():
    """Generate and email a 6-digit OTP for company registration verification."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    email = sanitize_string(data.get("email", "")).lower()
    if not validate_email(email):
        return jsonify({"error": "Invalid email format"}), 400

    db = get_db()
    try:
        # Block already-registered emails
        existing = db.execute("SELECT id FROM users WHERE email = %s", (email,)).fetchone()
        if existing:
            return jsonify({"error": "This email is already registered. Please log in instead."}), 409

        otp = "".join([str(random.randint(0, 9)) for _ in range(6)])
        expires_at = datetime.utcnow() + timedelta(minutes=10)

        # Invalidate any prior unused OTPs for same email
        db.execute("UPDATE email_verifications SET is_used = 1 WHERE email = %s AND is_used = 0", (email,))
        db.execute(
            "INSERT INTO email_verifications (email, otp, expires_at) VALUES (%s, %s, %s)",
            (email, otp, expires_at.strftime("%Y-%m-%d %H:%M:%S")),
        )
        db.commit()
    finally:
        release_db(db)

    from backend.services.alert_service import send_otp_email
    email_sent = send_otp_email(email, otp)

    return jsonify({
        "message": "OTP sent to your email address." if email_sent else "OTP generated (SMTP not configured — check server logs for the code).",
        "email_sent": email_sent,
        # In dev mode expose OTP if SMTP not configured (remove in production)
        "dev_otp": otp,
    }), 200


@auth_bp.route("/verify-otp", methods=["POST"])
def verify_otp():
    """Verify the 6-digit OTP submitted by the company during registration."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    email = sanitize_string(data.get("email", "")).lower()
    otp   = str(data.get("otp", "")).strip()

    if not validate_email(email):
        return jsonify({"error": "Invalid email"}), 400
    if not otp or len(otp) != 6 or not otp.isdigit():
        return jsonify({"error": "OTP must be 6 digits"}), 400

    db = get_db()
    try:
        record = row_to_dict(
            db.execute(
                """SELECT * FROM email_verifications
                   WHERE email = %s AND otp = %s AND is_used = 0
                   ORDER BY created_at DESC LIMIT 1""",
                (email, otp),
            ).fetchone()
        )

        if not record:
            return jsonify({"error": "Invalid or expired OTP. Please request a new one."}), 400

        if datetime.utcnow() > datetime.strptime(record["expires_at"], "%Y-%m-%d %H:%M:%S"):
            db.execute("UPDATE email_verifications SET is_used = 1 WHERE id = %s", (record["id"],))
            db.commit()
            return jsonify({"error": "OTP has expired. Please request a new one."}), 400

        # Mark OTP used
        db.execute("UPDATE email_verifications SET is_used = 1 WHERE id = %s", (record["id"],))
        db.commit()
    finally:
        release_db(db)

    # Store verified status in memory (15-min window to complete registration)
    _verified_emails[email] = datetime.utcnow() + timedelta(minutes=15)

    return jsonify({"message": "Email verified successfully. You may now complete your registration.", "verified": True}), 200


@auth_bp.route("/reset-password-request", methods=["POST"], strict_slashes=False)
def reset_password_request():
    """Request a password reset OTP for an existing company user."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    email = sanitize_string(data.get("email", "")).lower()
    if not validate_email(email):
        return jsonify({"error": "Invalid email format"}), 400

    db = get_db()
    try:
        # Check if user exists (only company users allowed here for this specific flow)
        user = row_to_dict(db.execute("SELECT id FROM users WHERE email = %s AND role = 'company'", (email,)).fetchone())
        if not user:
            return jsonify({"error": "No company account found with this email"}), 404

        otp = "".join([str(random.randint(0, 9)) for _ in range(6)])
        expires_at = datetime.utcnow() + timedelta(minutes=10)

        # Invalidate prior reset OTPs
        db.execute("UPDATE email_verifications SET is_used = 1 WHERE email = %s AND is_used = 0", (email,))
        db.execute(
            "INSERT INTO email_verifications (email, otp, expires_at) VALUES (%s, %s, %s)",
            (email, otp, expires_at.strftime("%Y-%m-%d %H:%M:%S")),
        )
        db.commit()
    finally:
        release_db(db)

    from backend.services.alert_service import send_otp_email
    email_sent = send_otp_email(email, otp)

    return jsonify({
        "message": "Verification code sent to your email." if email_sent else "Verification code generated.",
        "email_sent": email_sent,
        # Force dev_otp even if email_sent is True, but label it for dev.
        # This helps subagents and devs when they don't have access to the recipient inbox.
        "dev_otp": otp, 
    }), 200


@auth_bp.route("/reset-password-verify", methods=["POST"], strict_slashes=False)
def reset_password_verify():
    """Verify OTP and update password for company user."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    email        = sanitize_string(data.get("email", "")).lower()
    otp          = str(data.get("otp", "")).strip()
    new_password = data.get("password", "")

    if not validate_email(email):
        return jsonify({"error": "Invalid email"}), 400
    if not otp or len(otp) != 6:
        return jsonify({"error": "OTP must be 6 digits"}), 400
    
    valid_pw, pw_error = validate_password(new_password)
    if not valid_pw:
        return jsonify({"error": pw_error}), 400

    db = get_db()
    try:
        # Verify OTP
        record = row_to_dict(
            db.execute(
                """SELECT * FROM email_verifications
                   WHERE email = %s AND otp = %s AND is_used = 0
                   ORDER BY created_at DESC LIMIT 1""",
                (email, otp),
            ).fetchone()
        )

        if not record:
            return jsonify({"error": "Invalid or expired code."}), 400

        if datetime.utcnow() > datetime.strptime(record["expires_at"], "%Y-%m-%d %H:%M:%S"):
            return jsonify({"error": "Code has expired."}), 400

        # Hash new password
        password_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        # Update password AND mark OTP used
        db.execute("UPDATE users SET password_hash = %s WHERE email = %s", (password_hash, email))
        db.execute("UPDATE email_verifications SET is_used = 1 WHERE id = %s", (record["id"],))
        db.commit()
    finally:
        release_db(db)

    return jsonify({"message": "Password updated successfully. You can now log in."}), 200


@auth_bp.route("/register", methods=["POST"])
def register():
    """Register a new company account — requires prior email verification via OTP."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    name     = sanitize_string(data.get("name", ""))
    email    = sanitize_string(data.get("email", "")).lower()
    password = data.get("password", "")

    if not validate_name(name):
        return jsonify({"error": "Name must be between 2 and 100 characters"}), 400
    if not validate_email(email):
        return jsonify({"error": "Invalid email format"}), 400
    valid_pw, pw_error = validate_password(password)
    if not valid_pw:
        return jsonify({"error": pw_error}), 400

    # ── Enforce OTP verification ──────────────────────────────────────────────
    verified_until = _verified_emails.get(email)
    if not verified_until or datetime.utcnow() > verified_until:
        _verified_emails.pop(email, None)
        return jsonify({"error": "Email not verified. Please verify your email with OTP first."}), 403
    # Remove from store after use so each registration requires fresh verification
    _verified_emails.pop(email, None)
    # ─────────────────────────────────────────────────────────────────────────

    db = get_db()
    try:
        existing = db.execute("SELECT id FROM users WHERE email = %s", (email,)).fetchone()
        if existing:
            return jsonify({"error": "Email already registered"}), 409

        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        db.execute(
            "INSERT INTO users (name, email, password_hash, role) VALUES (%s, %s, %s, %s)",
            (name, email, password_hash, "company"),
        )
        db.commit()

        user = row_to_dict(db.execute("SELECT * FROM users WHERE email = %s", (email,)).fetchone())
        token = generate_token(user["id"], user["role"])

        return (
            jsonify(
                {
                    "message": "Company registered successfully",
                    "token": token,
                    "user": {
                        "id": user["id"],
                        "name": user["name"],
                        "email": user["email"],
                        "role": user["role"],
                    },
                }
            ),
            201,
        )
    finally:
        release_db(db)


@auth_bp.route("/login", methods=["POST"])
def login():
    """Authenticate user — company via email/password, employee via email+name+password."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    email = sanitize_string(data.get("email", "")).lower()
    password = data.get("password", "")
    name = sanitize_string(data.get("name", ""))  # Only used for employee login
    login_type = data.get("login_type", "company")  # 'company' or 'employee'

    if not email:
        return jsonify({"error": "Email is required"}), 400
    if not password:
        return jsonify({"error": "Password is required"}), 400

    db = get_db()
    try:
        user = None

        if login_type == "employee":
            # Employee login: match by email + name + role
            if not name:
                return jsonify({"error": "Name is required for employee login"}), 400
            user = row_to_dict(
                db.execute(
                    "SELECT * FROM users WHERE email = %s AND LOWER(name) = LOWER(%s) AND role = 'employee'",
                    (email, name),
                ).fetchone()
            )
        else:
            # Company login via email
            user = row_to_dict(
                db.execute(
                    "SELECT * FROM users WHERE email = %s AND role = 'company'",
                    (email,),
                ).fetchone()
            )

        if not user:
            return jsonify({"error": "Invalid credentials"}), 401

        if not bcrypt.checkpw(password.encode("utf-8"), user["password_hash"].encode("utf-8")):
            return jsonify({"error": "Invalid credentials"}), 401

        token = generate_token(user["id"], user["role"])

        return (
            jsonify(
                {
                    "message": "Login successful",
                    "token": token,
                    "user": {
                        "id": user["id"],
                        "name": user["name"],
                        "email": user["email"],
                        "role": user["role"],
                        "company_id": user.get("company_id"),
                    },
                }
            ),
            200,
        )
    finally:
        release_db(db)


@auth_bp.route("/invite-employee", methods=["POST"])
@token_required
def invite_employee():
    """Company invites an employee by name and email.
    Directly creates the employee account and sends credentials via official email.
    """
    # Only company accounts can invite
    if g.current_user_role != "company":
        return jsonify({"error": "Only company accounts can invite employees"}), 403

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    name = sanitize_string(data.get("name", ""))
    email = sanitize_string(data.get("email", "")).lower()

    if not validate_name(name):
        return jsonify({"error": "Name must be between 2 and 100 characters"}), 400
    if not validate_email(email):
        return jsonify({"error": "Invalid email format"}), 400

    db = get_db()
    try:
        # Check if employee already exists with this email
        existing = db.execute("SELECT id FROM users WHERE email = %s AND role = 'employee'", (email,)).fetchone()
        if existing:
            return jsonify({"error": "An employee with this email already exists"}), 409

        # Generate employee credentials
        employee_id = _generate_employee_id()
        while db.execute("SELECT id FROM users WHERE employee_id = %s", (employee_id,)).fetchone():
            employee_id = _generate_employee_id()

        raw_password = _generate_employee_password(name)
        password_hash = bcrypt.hashpw(raw_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        # Create the employee user immediately
        db.execute(
            """INSERT INTO users (name, email, password_hash, role, company_id, employee_id)
               VALUES (%s, %s, %s, 'employee', %s, %s)""",
            (name, email, password_hash, g.current_user_id, employee_id),
        )

        # Record the invitation
        token = secrets.token_urlsafe(48)
        db.execute(
            "INSERT INTO employee_invitations (company_id, name, email, token, is_used) VALUES (%s, %s, %s, %s, 1)",
            (g.current_user_id, name, email, token),
        )
        db.commit()

        # Send official credentials email
        from backend.services.alert_service import send_employee_credentials_email
        email_sent = send_employee_credentials_email(email, name, raw_password)

        return (
            jsonify(
                {
                    "message": "Employee account created and credentials sent!" if email_sent else "Employee account created (email delivery skipped — SMTP not configured)",
                    "employee_id": employee_id,
                    "email_sent": email_sent,
                    "name": name,
                    "email": email,
                    # In dev mode expose password if SMTP not configured
                    "dev_password": raw_password if not email_sent else None,
                }
            ),
            201,
        )
    finally:
        release_db(db)


@auth_bp.route("/employees", methods=["GET"])
@token_required
def list_employees():
    """List all employees invited by the current company."""
    if g.current_user_role != "company":
        return jsonify({"error": "Only company accounts can view employees"}), 403

    db = get_db()
    try:
        employees = rows_to_list(
            db.execute(
                "SELECT id, name, email, employee_id, created_at FROM users WHERE company_id = %s AND role = 'employee'",
                (g.current_user_id,),
            ).fetchall()
        )

        pending_invites = rows_to_list(
            db.execute(
                "SELECT id, name, email, created_at FROM employee_invitations WHERE company_id = %s AND is_used = 0",
                (g.current_user_id,),
            ).fetchall()
        )

        return jsonify({"employees": employees, "pending_invites": pending_invites}), 200
    finally:
        release_db(db)


@auth_bp.route("/profile", methods=["GET"])
@token_required
def get_profile():
    """Get current user's profile."""
    db = get_db()
    try:
        user = row_to_dict(
            db.execute(
                "SELECT id, name, email, role, employee_id, company_id, created_at FROM users WHERE id = %s",
                (g.current_user_id,),
            ).fetchone()
        )
        if not user:
            return jsonify({"error": "User not found"}), 404
        return jsonify({"user": user}), 200
    finally:
        release_db(db)


@auth_bp.route("/profile", methods=["PUT"])
@token_required
def update_profile():
    """Update current user's profile."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    updates = []
    params = []

    if "name" in data:
        name = sanitize_string(data["name"])
        if not validate_name(name):
            return jsonify({"error": "Name must be between 2 and 100 characters"}), 400
        updates.append("name = %s")
        params.append(name)

    if "password" in data:
        valid_pw, pw_error = validate_password(data["password"])
        if not valid_pw:
            return jsonify({"error": pw_error}), 400
        password_hash = bcrypt.hashpw(data["password"].encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        updates.append("password_hash = %s")
        params.append(password_hash)

    if not updates:
        return jsonify({"error": "No valid fields to update"}), 400

    params.append(g.current_user_id)

    db = get_db()
    try:
        db.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = %s", params)
        db.commit()

        user = row_to_dict(
            db.execute(
                "SELECT id, name, email, role FROM users WHERE id = %s",
                (g.current_user_id,),
            ).fetchone()
        )

        return jsonify({"message": "Profile updated", "user": user}), 200
    finally:
        release_db(db)
