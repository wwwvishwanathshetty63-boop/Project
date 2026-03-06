import bcrypt
import secrets
import string
import logging
from flask import Blueprint, request, jsonify, g
from backend.models import get_db, row_to_dict, rows_to_list
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


def _generate_random_password(length=10):
    """Generate a secure random password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    return "".join(secrets.choice(alphabet) for _ in range(length))


@auth_bp.route("/register", methods=["POST"])
def register():
    """Register a new company account."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    name = sanitize_string(data.get("name", ""))
    email = sanitize_string(data.get("email", "")).lower()
    password = data.get("password", "")

    if not validate_name(name):
        return jsonify({"error": "Name must be between 2 and 100 characters"}), 400
    if not validate_email(email):
        return jsonify({"error": "Invalid email format"}), 400
    valid_pw, pw_error = validate_password(password)
    if not valid_pw:
        return jsonify({"error": pw_error}), 400

    db = get_db()
    try:
        existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            return jsonify({"error": "Email already registered"}), 409

        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        db.execute(
            "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
            (name, email, password_hash, "company"),
        )
        db.commit()

        user = row_to_dict(db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone())
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
        db.close()


@auth_bp.route("/login", methods=["POST"])
def login():
    """Authenticate user (company via email or employee via employee_id)."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    employee_id = data.get("employee_id", "").strip()
    email = sanitize_string(data.get("email", "")).lower()
    password = data.get("password", "")

    if not password:
        return jsonify({"error": "Password is required"}), 400

    db = get_db()
    try:
        user = None

        if employee_id:
            # Employee login via employee ID
            user = row_to_dict(
                db.execute("SELECT * FROM users WHERE employee_id = ?", (employee_id,)).fetchone()
            )
        elif email:
            # Company login via email
            user = row_to_dict(
                db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            )
        else:
            return jsonify({"error": "Email or Employee ID is required"}), 400

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
                        "employee_id": user.get("employee_id"),
                    },
                }
            ),
            200,
        )
    finally:
        db.close()


@auth_bp.route("/invite-employee", methods=["POST"])
@token_required
def invite_employee():
    """Company invites an employee by name and email. Sends an invitation email."""
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
        existing = db.execute("SELECT id FROM users WHERE email = ? AND role = 'employee'", (email,)).fetchone()
        if existing:
            return jsonify({"error": "An employee with this email already exists"}), 409

        # Check if there's already a pending invite for this email from this company
        pending = db.execute(
            "SELECT id FROM employee_invitations WHERE email = ? AND company_id = ? AND is_used = 0",
            (email, g.current_user_id),
        ).fetchone()
        if pending:
            return jsonify({"error": "An invitation is already pending for this email"}), 409

        # Generate secure token
        token = secrets.token_urlsafe(48)

        db.execute(
            "INSERT INTO employee_invitations (company_id, name, email, token) VALUES (?, ?, ?, ?)",
            (g.current_user_id, name, email, token),
        )
        db.commit()

        # Send invitation email
        from backend.services.alert_service import send_invitation_email
        email_sent = send_invitation_email(email, name, token)

        return (
            jsonify(
                {
                    "message": "Invitation sent successfully" if email_sent else "Invitation created (email delivery skipped — SMTP not configured)",
                    "token": token,  # Useful for development/testing
                    "email_sent": email_sent,
                }
            ),
            201,
        )
    finally:
        db.close()


@auth_bp.route("/verify-employee", methods=["POST"])
def verify_employee():
    """Verify an employee invitation token and auto-generate credentials."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    token = data.get("token", "").strip()
    if not token:
        return jsonify({"error": "Invitation token is required"}), 400

    db = get_db()
    try:
        invitation = row_to_dict(
            db.execute(
                "SELECT * FROM employee_invitations WHERE token = ?", (token,)
            ).fetchone()
        )

        if not invitation:
            return jsonify({"error": "Invalid invitation link"}), 404

        if invitation["is_used"]:
            return jsonify({"error": "This invitation has already been used"}), 410

        # Check if email already registered as employee
        existing = db.execute(
            "SELECT id FROM users WHERE email = ?", (invitation["email"],)
        ).fetchone()
        if existing:
            # Mark invite used and return error
            db.execute("UPDATE employee_invitations SET is_used = 1 WHERE id = ?", (invitation["id"],))
            db.commit()
            return jsonify({"error": "This email is already registered"}), 409

        # Generate employee credentials
        employee_id = _generate_employee_id()
        # Make sure employee_id is unique
        while db.execute("SELECT id FROM users WHERE employee_id = ?", (employee_id,)).fetchone():
            employee_id = _generate_employee_id()

        raw_password = _generate_random_password()
        password_hash = bcrypt.hashpw(raw_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        # Create the employee user
        db.execute(
            """INSERT INTO users (name, email, password_hash, role, company_id, employee_id)
               VALUES (?, ?, ?, 'employee', ?, ?)""",
            (invitation["name"], invitation["email"], password_hash, invitation["company_id"], employee_id),
        )

        # Mark invitation as used
        db.execute("UPDATE employee_invitations SET is_used = 1 WHERE id = ?", (invitation["id"],))
        db.commit()

        return (
            jsonify(
                {
                    "message": "Account created successfully! Save your credentials below.",
                    "employee_id": employee_id,
                    "password": raw_password,
                    "name": invitation["name"],
                }
            ),
            201,
        )
    finally:
        db.close()


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
                "SELECT id, name, email, employee_id, created_at FROM users WHERE company_id = ? AND role = 'employee'",
                (g.current_user_id,),
            ).fetchall()
        )

        pending_invites = rows_to_list(
            db.execute(
                "SELECT id, name, email, created_at FROM employee_invitations WHERE company_id = ? AND is_used = 0",
                (g.current_user_id,),
            ).fetchall()
        )

        return jsonify({"employees": employees, "pending_invites": pending_invites}), 200
    finally:
        db.close()


@auth_bp.route("/profile", methods=["GET"])
@token_required
def get_profile():
    """Get current user's profile."""
    db = get_db()
    try:
        user = row_to_dict(
            db.execute(
                "SELECT id, name, email, role, employee_id, company_id, created_at FROM users WHERE id = ?",
                (g.current_user_id,),
            ).fetchone()
        )
        if not user:
            return jsonify({"error": "User not found"}), 404
        return jsonify({"user": user}), 200
    finally:
        db.close()


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
        updates.append("name = ?")
        params.append(name)

    if "password" in data:
        valid_pw, pw_error = validate_password(data["password"])
        if not valid_pw:
            return jsonify({"error": pw_error}), 400
        password_hash = bcrypt.hashpw(data["password"].encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        updates.append("password_hash = ?")
        params.append(password_hash)

    if not updates:
        return jsonify({"error": "No valid fields to update"}), 400

    params.append(g.current_user_id)

    db = get_db()
    try:
        db.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
        db.commit()

        user = row_to_dict(
            db.execute(
                "SELECT id, name, email, role FROM users WHERE id = ?",
                (g.current_user_id,),
            ).fetchone()
        )

        return jsonify({"message": "Profile updated", "user": user}), 200
    finally:
        db.close()
