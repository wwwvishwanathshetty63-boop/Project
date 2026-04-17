import uuid
from flask import Blueprint, request, jsonify, g
from backend.models import get_db, row_to_dict, rows_to_list, release_db, release_db
from backend.utils.auth import token_required
from backend.utils.validators import (
    validate_url,
    validate_name,
    validate_http_method,
    validate_interval,
    sanitize_string,
)

endpoint_bp = Blueprint("endpoints", __name__, url_prefix="/api/endpoints")


@endpoint_bp.route("", methods=["POST"])
@token_required
def create_endpoint():
    """Add a new API endpoint for monitoring."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    name = sanitize_string(data.get("name", ""))
    url = sanitize_string(data.get("url", ""))
    method = sanitize_string(data.get("method", "GET")).upper()
    interval = data.get("interval", 60)
    api_key = data.get("api_key", None)
    api_key_header = sanitize_string(data.get("api_key_header", "Authorization"))

    if not validate_name(name):
        return jsonify({"error": "Name must be between 2 and 100 characters"}), 400
    if not validate_url(url):
        return jsonify({"error": "Invalid URL format (must start with http or https)"}), 400
    if not validate_http_method(method):
        return jsonify({"error": "Invalid HTTP method"}), 400
    if not validate_interval(interval):
        return jsonify({"error": "Interval must be between 30 and 3600 seconds"}), 400

    endpoint_id = uuid.uuid4().hex
    db = get_db()
    try:
        db.execute(
            "INSERT INTO api_endpoints (id, user_id, name, url, method, interval, is_active, api_key, api_key_header) VALUES (%s, %s, %s, %s, %s, %s, 1, %s, %s)",
            (endpoint_id, g.current_user_id, name, url, method, int(interval), api_key, api_key_header),
        )
        db.commit()

        endpoint = row_to_dict(
            db.execute(
                "SELECT * FROM api_endpoints WHERE id = %s",
                (endpoint_id,),
            ).fetchone()
        )
        endpoint["is_active"] = bool(endpoint["is_active"])

        return jsonify({"message": "Endpoint created", "endpoint": endpoint}), 201
    finally:
        release_db(db)


@endpoint_bp.route("", methods=["GET"])
@token_required
def list_endpoints():
    """List all API endpoints for the current user with stats."""
    db = get_db()
    try:
        # 1. Get all endpoints for user
        rows = db.execute(
            "SELECT * FROM api_endpoints WHERE user_id = %s ORDER BY created_at DESC",
            (g.current_user_id,),
        ).fetchall()
        endpoints = rows_to_list(rows)

        if not endpoints:
            return jsonify({"endpoints": []}), 200

        # 2. Get range from query (default 1d)
        time_range = request.args.get("range", "1d")
        days = {"1d": 1, "7d": 7, "30d": 30}.get(time_range, 1)
        since = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

        # 3. Fetch aggregate stats for the range
        endpoint_ids = [e["id"] for e in endpoints]
        placeholders = ",".join(["%s"] * len(endpoint_ids))
        
        stats_rows = db.execute(
            f"""
            SELECT 
                endpoint_id,
                COUNT(*) as total,
                SUM(CASE WHEN is_success = 1 THEN 1 ELSE 0 END) as successes,
                AVG(response_time) as avg_rt
            FROM monitoring_logs 
            WHERE endpoint_id IN ({placeholders}) AND checked_at >= %s
            GROUP BY endpoint_id
            """,
            (*endpoint_ids, since)
        ).fetchall()
        stats_dict = {row["endpoint_id"]: row for row in stats_rows}

        # 4. Fetch LATEST log for current status
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
            (*endpoint_ids,)
        ).fetchall()
        latest_dict = {row["endpoint_id"]: row for row in latest_rows}

        # 5. Combine data
        for ep in endpoints:
            ep["is_active"] = bool(ep["is_active"])
            
            # Aggregate stats
            s = stats_dict.get(ep["id"])
            if s and s["total"] > 0:
                ep["uptime_percentage"] = round((s["successes"] / s["total"]) * 100, 2)
            else:
                ep["uptime_percentage"] = 100.0

            # Latest status
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

        return jsonify({"endpoints": endpoints}), 200
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500
    finally:
        release_db(db)


@endpoint_bp.route("/<endpoint_id>", methods=["GET"])
@token_required
def get_endpoint(endpoint_id):
    """Get a specific API endpoint."""
    db = get_db()
    try:
        row = db.execute(
            "SELECT * FROM api_endpoints WHERE id = %s AND user_id = %s",
            (endpoint_id, g.current_user_id),
        ).fetchone()

        if not row:
            return jsonify({"error": "Endpoint not found"}), 404

        endpoint = row_to_dict(row)
        endpoint["is_active"] = bool(endpoint["is_active"])
        return jsonify({"endpoint": endpoint}), 200
    finally:
        release_db(db)


@endpoint_bp.route("/<endpoint_id>", methods=["PUT"])
@token_required
def update_endpoint(endpoint_id):
    """Update an API endpoint."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    db = get_db()
    try:
        existing = db.execute(
            "SELECT id FROM api_endpoints WHERE id = %s AND user_id = %s",
            (endpoint_id, g.current_user_id),
        ).fetchone()
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
            if not validate_url(url):
                return jsonify({"error": "Invalid URL"}), 400
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
        if "api_key" in data:
            # We can allow clearing the api_key if they send ''
            updates.append("api_key = %s")
            params.append(data["api_key"] if data["api_key"] else None)
        if "api_key_header" in data:
            updates.append("api_key_header = %s")
            params.append(sanitize_string(data["api_key_header"]))

        if not updates:
            return jsonify({"error": "No valid fields to update"}), 400

        params.append(endpoint_id)
        db.execute(f"UPDATE api_endpoints SET {', '.join(updates)} WHERE id = %s", params)
        db.commit()

        endpoint = row_to_dict(
            db.execute("SELECT * FROM api_endpoints WHERE id = %s", (endpoint_id,)).fetchone()
        )
        endpoint["is_active"] = bool(endpoint["is_active"])

        return jsonify({"message": "Endpoint updated", "endpoint": endpoint}), 200
    finally:
        release_db(db)


@endpoint_bp.route("/<endpoint_id>", methods=["DELETE"])
@token_required
def delete_endpoint(endpoint_id):
    """Delete an API endpoint."""
    db = get_db()
    try:
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
        release_db(db)


@endpoint_bp.route("/<endpoint_id>/toggle", methods=["PATCH"])
@token_required
def toggle_endpoint(endpoint_id):
    """Enable or disable monitoring for an endpoint."""
    db = get_db()
    try:
        existing = db.execute(
            "SELECT id, is_active FROM api_endpoints WHERE id = %s AND user_id = %s",
            (endpoint_id, g.current_user_id),
        ).fetchone()
        if not existing:
            return jsonify({"error": "Endpoint not found"}), 404

        new_status = 0 if existing["is_active"] else 1
        db.execute("UPDATE api_endpoints SET is_active = %s WHERE id = %s", (new_status, endpoint_id))
        db.commit()

        endpoint = row_to_dict(
            db.execute("SELECT * FROM api_endpoints WHERE id = %s", (endpoint_id,)).fetchone()
        )
        endpoint["is_active"] = bool(endpoint["is_active"])
        status_text = "enabled" if new_status else "disabled"

        return jsonify({"message": f"Monitoring {status_text}", "endpoint": endpoint}), 200
    finally:
        release_db(db)


@endpoint_bp.route("/<endpoint_id>/logs", methods=["GET"])
@token_required
def get_endpoint_logs(endpoint_id):
    """Get monitoring logs for a specific endpoint."""
    db = get_db()
    try:
        existing = db.execute(
            "SELECT id FROM api_endpoints WHERE id = %s AND user_id = %s",
            (endpoint_id, g.current_user_id, ),
        ).fetchone()
        if not existing:
            return jsonify({"error": "Endpoint not found"}), 404

        time_range = request.args.get("range", "1d")
        days_map = {"1d": 1, "7d": 7, "30d": 30}
        days = days_map.get(time_range, 1)

        since = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        limit = request.args.get("limit", 100, type=int)
        limit = min(limit, 1000)

        logs = rows_to_list(
            db.execute(
                "SELECT * FROM monitoring_logs WHERE endpoint_id = %s AND checked_at >= %s ORDER BY checked_at DESC LIMIT %s",
                (endpoint_id, since, limit),
            ).fetchall()
        )

        for log in logs:
            log["is_success"] = bool(log["is_success"])

        return jsonify({"logs": logs}), 200
    finally:
        release_db(db)
