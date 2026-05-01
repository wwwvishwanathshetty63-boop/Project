"""Endpoint CRUD routes — accepts all API keys and URLs without validation."""
import uuid
import datetime
from flask import Blueprint, request, jsonify, g
from backend.models import get_db, row_to_dict, rows_to_list, release_db
from backend.utils.auth import token_required
from backend.utils.validators import (
    validate_name,
    validate_http_method,
    validate_interval,
    sanitize_string,
)
from backend.services.api_key_validator import mask_api_key
from backend.services.ai_detector import detect_api_url_from_key
from backend.services.cache_service import cache, build_key, TTL_ENDPOINTS, TTL_LOGS

endpoint_bp = Blueprint("endpoints", __name__, url_prefix="/api/endpoints")


# ── Helpers ──────────────────────────────────────────────────

def _mask_endpoint(endpoint: dict) -> dict:
    """Strip the raw API key from any outgoing response."""
    if endpoint and endpoint.get("api_key"):
        endpoint["api_key_masked"] = mask_api_key(endpoint["api_key"])
        endpoint["api_key"] = None  # NEVER leak full key
    return endpoint


# ── POST /api/endpoints/detect-url ───────────────────────────

@endpoint_bp.route("/detect-url", methods=["POST"])
@token_required
def detect_url():
    """Use AI to auto-detect base URL from an API key format."""
    data = request.get_json()
    if not data or not data.get("api_key"):
        return jsonify({"error": "api_key is required"}), 400
        
    result = detect_api_url_from_key(data["api_key"])
    if not result["success"]:
        return jsonify({"error": result["error"]}), 400
        
    return jsonify({
        "provider": result["provider"],
        "base_url": result["base_url"]
    }), 200


# ── POST  /api/endpoints ─────────────────────────────────────

@endpoint_bp.route("", methods=["POST"])
@token_required
def create_endpoint():
    """Add a new API endpoint for monitoring — rejects dummy keys."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    name = sanitize_string(data.get("name", ""))
    url = sanitize_string(data.get("url", ""))
    method = sanitize_string(data.get("method", "GET")).upper()
    interval = data.get("interval", 60)
    api_key = data.get("api_key", None)
    api_key_header = sanitize_string(data.get("api_key_header", "Authorization"))
    auth_type = sanitize_string(data.get("auth_type", "header"))

    if not validate_name(name):
        return jsonify({"error": "Name must be between 2 and 100 characters"}), 400
    if not url.startswith("http"):
        url = "https://" + url



    if not validate_http_method(method):
        return jsonify({"error": "Invalid HTTP method"}), 400
    if not validate_interval(interval):
        return jsonify({"error": "Interval must be between 30 and 3600 seconds"}), 400

    key_status = None
    last_validated_at = None
    if api_key:
        key_status = "VALID"
        last_validated_at = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S"
        )


    endpoint_id = uuid.uuid4().hex
    db = get_db()
    try:
        # Employees: endpoint is "owned" by company for monitoring,
        # but created_by tracks the individual employee.
        owner_id = g.current_user_id
        if g.current_user_role == "employee":
            user_row = row_to_dict(
                db.execute("SELECT company_id FROM users WHERE id = %s", (g.current_user_id,)).fetchone()
            )
            if user_row and user_row.get("company_id"):
                owner_id = user_row["company_id"]

        db.execute(
            """INSERT INTO api_endpoints
               (id, user_id, created_by, name, url, method, interval, is_active,
                api_key, api_key_header, auth_type, key_status, last_validated_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, %s, %s, %s, %s, %s)""",
            (
                endpoint_id, owner_id, g.current_user_id, name, url, method, int(interval),
                api_key, api_key_header, auth_type, key_status, last_validated_at,
            ),
        )
        db.commit()

        endpoint = row_to_dict(
            db.execute(
                "SELECT * FROM api_endpoints WHERE id = %s",
                (endpoint_id,),
            ).fetchone()
        )
        endpoint["is_active"] = bool(endpoint["is_active"])
        _mask_endpoint(endpoint)

        return jsonify({"message": "Endpoint created", "endpoint": endpoint}), 201
    finally:
        cache.invalidate("stats:")
        cache.invalidate("chart:")
        cache.invalidate("endpoints:")
        cache.invalidate("analytics:")
        cache.invalidate("company_activity:")
        release_db(db)


# ── GET  /api/endpoints ──────────────────────────────────────

@endpoint_bp.route("", methods=["GET"])
@token_required
def list_endpoints():
    """List API endpoints for the current user with stats (cached 20s)."""
    time_range = request.args.get("range", "1d")
    cache_key = build_key("endpoints", g.current_user_id, time_range)
    cached = cache.get(cache_key)
    if cached:
        return jsonify(cached), 200

    db = get_db()
    try:
        # Employees see only endpoints THEY created.
        # Company admins see all endpoints they own.
        if g.current_user_role == "employee":
            rows = db.execute(
                "SELECT * FROM api_endpoints WHERE created_by = %s ORDER BY created_at DESC",
                (g.current_user_id,),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM api_endpoints WHERE user_id = %s ORDER BY created_at DESC",
                (g.current_user_id,),
            ).fetchall()
        endpoints = rows_to_list(rows)

        if not endpoints:
            return jsonify({"endpoints": []}), 200

        time_range = request.args.get("range", "1d")
        days = {"1d": 1, "7d": 7, "30d": 30}.get(time_range, 1)
        since = (
            datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(days=days)
        ).strftime("%Y-%m-%d %H:%M:%S")

        endpoint_ids = [e["id"] for e in endpoints]
        placeholders = ",".join(["%s"] * len(endpoint_ids))

        stats_rows = db.execute(
            f"""
            SELECT
                endpoint_id,
                COUNT(*) as total,
                SUM(CASE WHEN is_success = TRUE THEN 1 ELSE 0 END) as successes,
                AVG(response_time) as avg_rt
            FROM monitoring_logs
            WHERE endpoint_id IN ({placeholders}) AND checked_at >= %s
            GROUP BY endpoint_id
            """,
            (*endpoint_ids, since),
        ).fetchall()
        stats_dict = {row["endpoint_id"]: row for row in stats_rows}

        latest_rows = db.execute(
            f"""
            SELECT l1.*
            FROM monitoring_logs l1
            JOIN (
                SELECT endpoint_id, MAX(checked_at) as max_at
                FROM monitoring_logs
                WHERE endpoint_id IN ({placeholders})
                GROUP BY endpoint_id
            ) l2 ON l1.endpoint_id = l2.endpoint_id AND l1.checked_at = l2.max_at
            """,
            (*endpoint_ids,),
        ).fetchall()
        latest_dict = {row["endpoint_id"]: row for row in latest_rows}

        for ep in endpoints:
            ep["is_active"] = bool(ep["is_active"])
            _mask_endpoint(ep)

            s = stats_dict.get(ep["id"])
            if s and s["total"] > 0:
                ep["uptime_percentage"] = round((s["successes"] / s["total"]) * 100, 2)
            else:
                ep["uptime_percentage"] = 100.0

            l = latest_dict.get(ep["id"])
            if l:
                ep["is_down"] = not bool(l["is_success"])
                ep["last_check"] = l["checked_at"]
                ep["last_response_time"] = l["response_time"]
                ep["last_status_code"] = l["status_code"]
            else:
                ep["is_down"] = False
                ep["last_check"] = None
                ep["last_response_time"] = None
                ep["last_status_code"] = None

        result = {"endpoints": endpoints}
        cache.set(cache_key, result, ttl=TTL_ENDPOINTS)
        return jsonify(result), 200
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500
    finally:
        release_db(db)


# ── GET  /api/endpoints/<id> ─────────────────────────────────

@endpoint_bp.route("/<endpoint_id>", methods=["GET"])
@token_required
def get_endpoint(endpoint_id):
    """Get a specific API endpoint."""
    db = get_db()
    try:
        if g.current_user_role == "employee":
            row = db.execute(
                "SELECT * FROM api_endpoints WHERE id = %s AND created_by = %s",
                (endpoint_id, g.current_user_id),
            ).fetchone()
        else:
            row = db.execute(
                "SELECT * FROM api_endpoints WHERE id = %s AND user_id = %s",
                (endpoint_id, g.current_user_id),
            ).fetchone()

        if not row:
            return jsonify({"error": "Endpoint not found"}), 404

        endpoint = row_to_dict(row)
        endpoint["is_active"] = bool(endpoint["is_active"])
        _mask_endpoint(endpoint)
        return jsonify({"endpoint": endpoint}), 200
    finally:
        release_db(db)


# ── PUT  /api/endpoints/<id> ─────────────────────────────────

@endpoint_bp.route("/<endpoint_id>", methods=["PUT"])
@token_required
def update_endpoint(endpoint_id):
    """Update an API endpoint — re-validates key if changed."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    db = get_db()
    try:
        if g.current_user_role == "employee":
            existing = row_to_dict(
                db.execute(
                    "SELECT * FROM api_endpoints WHERE id = %s AND created_by = %s",
                    (endpoint_id, g.current_user_id),
                ).fetchone()
            )
        else:
            existing = row_to_dict(
                db.execute(
                    "SELECT * FROM api_endpoints WHERE id = %s AND user_id = %s",
                    (endpoint_id, g.current_user_id),
                ).fetchone()
            )
        if not existing:
            return jsonify({"error": "Endpoint not found"}), 404

        updates = []
        params = []

        if "name" in data:
            name = sanitize_string(data["name"])
            if not validate_name(name):
                return jsonify({"error": "Invalid name"}), 400
            updates.append("name = %s")
            params.append(name)
        if "url" in data:
            url = sanitize_string(data["url"])
            if not url.startswith("http"):
                url = "https://" + url
            

            
            updates.append("url = %s")
            params.append(url)
        if "method" in data:
            method = sanitize_string(data["method"]).upper()
            if not validate_http_method(method):
                return jsonify({"error": "Invalid HTTP method"}), 400
            updates.append("method = %s")
            params.append(method)
        if "interval" in data:
            if not validate_interval(data["interval"]):
                return jsonify({"error": "Invalid interval"}), 400
            updates.append("interval = %s")
            params.append(int(data["interval"]))
        if "api_key_header" in data:
            updates.append("api_key_header = %s")
            params.append(sanitize_string(data["api_key_header"]))
        if "auth_type" in data:
            updates.append("auth_type = %s")
            params.append(sanitize_string(data["auth_type"]))

        # Save API key directly — no validation
        if "api_key" in data:
            new_key = data["api_key"] if data["api_key"] else None
            if new_key:
                updates.append("api_key = %s")
                params.append(new_key)
                updates.append("key_status = %s")
                params.append("VALID")
                updates.append("last_validated_at = %s")
                params.append(
                    datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                )
            else:
                # Clearing the key
                updates.append("api_key = %s")
                params.append(None)
                updates.append("key_status = %s")
                params.append(None)
                updates.append("last_validated_at = %s")
                params.append(None)

        if not updates:
            return jsonify({"error": "No valid fields to update"}), 400

        params.append(endpoint_id)
        db.execute(
            f"UPDATE api_endpoints SET {', '.join(updates)} WHERE id = %s", params
        )
        db.commit()

        endpoint = row_to_dict(
            db.execute("SELECT * FROM api_endpoints WHERE id = %s", (endpoint_id,)).fetchone()
        )
        endpoint["is_active"] = bool(endpoint["is_active"])
        _mask_endpoint(endpoint)

        return jsonify({"message": "Endpoint updated", "endpoint": endpoint}), 200
    finally:
        cache.invalidate("stats:")
        cache.invalidate("chart:")
        cache.invalidate("endpoints:")
        cache.invalidate("analytics:")
        cache.invalidate("company_activity:")
        cache.invalidate(f"emp_endpoints:")
        cache.invalidate(f"logs:{endpoint_id}")
        release_db(db)


# ── DELETE  /api/endpoints/<id> ──────────────────────────────

@endpoint_bp.route("/<endpoint_id>", methods=["DELETE"])
@token_required
def delete_endpoint(endpoint_id):
    """Delete an API endpoint."""
    db = get_db()
    try:
        if g.current_user_role == "employee":
            existing = db.execute(
                "SELECT id FROM api_endpoints WHERE id = %s AND created_by = %s",
                (endpoint_id, g.current_user_id),
            ).fetchone()
        else:
            existing = db.execute(
                "SELECT id FROM api_endpoints WHERE id = %s AND user_id = %s",
                (endpoint_id, g.current_user_id),
            ).fetchone()
        if not existing:
            return jsonify({"error": "Endpoint not found"}), 404

        db.execute("DELETE FROM monitoring_logs WHERE endpoint_id = %s", (endpoint_id,))
        db.execute("DELETE FROM api_endpoints WHERE id = %s", (endpoint_id,))
        db.commit()

        return jsonify({"message": "Endpoint deleted"}), 200
    finally:
        cache.invalidate("stats:")
        cache.invalidate("chart:")
        cache.invalidate("endpoints:")
        cache.invalidate("analytics:")
        cache.invalidate("company_activity:")
        cache.invalidate("emp_endpoints:")
        cache.delete(build_key("logs", endpoint_id))
        release_db(db)


# ── PATCH  /api/endpoints/<id>/toggle ────────────────────────

@endpoint_bp.route("/<endpoint_id>/toggle", methods=["PATCH"])
@token_required
def toggle_endpoint(endpoint_id):
    """Enable or disable monitoring for an endpoint."""
    db = get_db()
    try:
        if g.current_user_role == "employee":
            existing = db.execute(
                "SELECT id, is_active FROM api_endpoints WHERE id = %s AND created_by = %s",
                (endpoint_id, g.current_user_id),
            ).fetchone()
        else:
            existing = db.execute(
                "SELECT id, is_active FROM api_endpoints WHERE id = %s AND user_id = %s",
                (endpoint_id, g.current_user_id),
            ).fetchone()
        if not existing:
            return jsonify({"error": "Endpoint not found"}), 404

        new_status = False if existing["is_active"] else True
        db.execute(
            "UPDATE api_endpoints SET is_active = %s WHERE id = %s",
            (new_status, endpoint_id),
        )
        db.commit()

        endpoint = row_to_dict(
            db.execute("SELECT * FROM api_endpoints WHERE id = %s", (endpoint_id,)).fetchone()
        )
        endpoint["is_active"] = bool(endpoint["is_active"])
        _mask_endpoint(endpoint)
        status_text = "enabled" if new_status else "disabled"

        return jsonify({"message": f"Monitoring {status_text}", "endpoint": endpoint}), 200
    finally:
        cache.invalidate("stats:")
        cache.invalidate("endpoints:")
        cache.invalidate("analytics:")
        cache.invalidate("company_activity:")
        release_db(db)


# ── GET  /api/endpoints/<id>/logs ────────────────────────────

@endpoint_bp.route("/<endpoint_id>/logs", methods=["GET"])
@token_required
def get_endpoint_logs(endpoint_id):
    """Get monitoring logs for a specific endpoint (cached 10s)."""
    time_range = request.args.get("range", "1d")
    limit       = request.args.get("limit", 100, type=int)
    limit       = min(limit, 1000)
    cache_key   = build_key("logs", endpoint_id, time_range, limit)
    cached      = cache.get(cache_key)
    if cached:
        return jsonify(cached), 200

    db = get_db()
    try:
        if g.current_user_role == "employee":
            existing = db.execute(
                "SELECT id FROM api_endpoints WHERE id = %s AND created_by = %s",
                (endpoint_id, g.current_user_id),
            ).fetchone()
        else:
            existing = db.execute(
                "SELECT id FROM api_endpoints WHERE id = %s AND user_id = %s",
                (endpoint_id, g.current_user_id),
            ).fetchone()
        if not existing:
            return jsonify({"error": "Endpoint not found"}), 404

        days_map = {"1d": 1, "7d": 7, "30d": 30}
        days = days_map.get(time_range, 1)

        since = (
            datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
        ).strftime("%Y-%m-%d %H:%M:%S")

        logs = rows_to_list(
            db.execute(
                "SELECT * FROM monitoring_logs WHERE endpoint_id = %s AND checked_at >= %s ORDER BY checked_at DESC LIMIT %s",
                (endpoint_id, since, limit),
            ).fetchall()
        )

        for log in logs:
            log["is_success"] = bool(log["is_success"])

        result = {"logs": logs}
        cache.set(cache_key, result, ttl=TTL_LOGS)
        return jsonify(result), 200
    finally:
        release_db(db)
