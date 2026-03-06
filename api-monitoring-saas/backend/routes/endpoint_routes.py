import uuid
from flask import Blueprint, request, jsonify, g
from backend.models import get_db, row_to_dict, rows_to_list
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
            "INSERT INTO api_endpoints (id, user_id, name, url, method, interval, is_active) VALUES (?, ?, ?, ?, ?, ?, 1)",
            (endpoint_id, g.current_user_id, name, url, method, int(interval)),
        )
        db.commit()

        endpoint = row_to_dict(
            db.execute(
                "SELECT * FROM api_endpoints WHERE id = ?",
                (endpoint_id,),
            ).fetchone()
        )
        endpoint["is_active"] = bool(endpoint["is_active"])

        return jsonify({"message": "Endpoint created", "endpoint": endpoint}), 201
    finally:
        db.close()


@endpoint_bp.route("", methods=["GET"])
@token_required
def list_endpoints():
    """List all API endpoints for the current user."""
    db = get_db()
    try:
        rows = db.execute(
            "SELECT * FROM api_endpoints WHERE user_id = ? ORDER BY created_at DESC",
            (g.current_user_id,),
        ).fetchall()

        endpoints = rows_to_list(rows)
        for ep in endpoints:
            ep["is_active"] = bool(ep["is_active"])

        return jsonify({"endpoints": endpoints}), 200
    finally:
        db.close()


@endpoint_bp.route("/<endpoint_id>", methods=["GET"])
@token_required
def get_endpoint(endpoint_id):
    """Get a specific API endpoint."""
    db = get_db()
    try:
        row = db.execute(
            "SELECT * FROM api_endpoints WHERE id = ? AND user_id = ?",
            (endpoint_id, g.current_user_id),
        ).fetchone()

        if not row:
            return jsonify({"error": "Endpoint not found"}), 404

        endpoint = row_to_dict(row)
        endpoint["is_active"] = bool(endpoint["is_active"])
        return jsonify({"endpoint": endpoint}), 200
    finally:
        db.close()


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
            "SELECT id FROM api_endpoints WHERE id = ? AND user_id = ?",
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
            updates.append("name = ?")
            params.append(name)
        if "url" in data:
            url = sanitize_string(data["url"])
            if not validate_url(url):
                return jsonify({"error": "Invalid URL"}), 400
            updates.append("url = ?")
            params.append(url)
        if "method" in data:
            method = sanitize_string(data["method"]).upper()
            if not validate_http_method(method):
                return jsonify({"error": "Invalid HTTP method"}), 400
            updates.append("method = ?")
            params.append(method)
        if "interval" in data:
            if not validate_interval(data["interval"]):
                return jsonify({"error": "Invalid interval"}), 400
            updates.append("interval = ?")
            params.append(int(data["interval"]))

        if not updates:
            return jsonify({"error": "No valid fields to update"}), 400

        params.append(endpoint_id)
        db.execute(f"UPDATE api_endpoints SET {', '.join(updates)} WHERE id = ?", params)
        db.commit()

        endpoint = row_to_dict(
            db.execute("SELECT * FROM api_endpoints WHERE id = ?", (endpoint_id,)).fetchone()
        )
        endpoint["is_active"] = bool(endpoint["is_active"])

        return jsonify({"message": "Endpoint updated", "endpoint": endpoint}), 200
    finally:
        db.close()


@endpoint_bp.route("/<endpoint_id>", methods=["DELETE"])
@token_required
def delete_endpoint(endpoint_id):
    """Delete an API endpoint."""
    db = get_db()
    try:
        existing = db.execute(
            "SELECT id FROM api_endpoints WHERE id = ? AND user_id = ?",
            (endpoint_id, g.current_user_id),
        ).fetchone()
        if not existing:
            return jsonify({"error": "Endpoint not found"}), 404

        db.execute("DELETE FROM monitoring_logs WHERE endpoint_id = ?", (endpoint_id,))
        db.execute("DELETE FROM api_endpoints WHERE id = ?", (endpoint_id,))
        db.commit()

        return jsonify({"message": "Endpoint deleted"}), 200
    finally:
        db.close()


@endpoint_bp.route("/<endpoint_id>/toggle", methods=["PATCH"])
@token_required
def toggle_endpoint(endpoint_id):
    """Enable or disable monitoring for an endpoint."""
    db = get_db()
    try:
        existing = db.execute(
            "SELECT id, is_active FROM api_endpoints WHERE id = ? AND user_id = ?",
            (endpoint_id, g.current_user_id),
        ).fetchone()
        if not existing:
            return jsonify({"error": "Endpoint not found"}), 404

        new_status = 0 if existing["is_active"] else 1
        db.execute("UPDATE api_endpoints SET is_active = ? WHERE id = ?", (new_status, endpoint_id))
        db.commit()

        endpoint = row_to_dict(
            db.execute("SELECT * FROM api_endpoints WHERE id = ?", (endpoint_id,)).fetchone()
        )
        endpoint["is_active"] = bool(endpoint["is_active"])
        status_text = "enabled" if new_status else "disabled"

        return jsonify({"message": f"Monitoring {status_text}", "endpoint": endpoint}), 200
    finally:
        db.close()


@endpoint_bp.route("/<endpoint_id>/logs", methods=["GET"])
@token_required
def get_endpoint_logs(endpoint_id):
    """Get monitoring logs for a specific endpoint."""
    db = get_db()
    try:
        existing = db.execute(
            "SELECT id FROM api_endpoints WHERE id = ? AND user_id = ?",
            (endpoint_id, g.current_user_id),
        ).fetchone()
        if not existing:
            return jsonify({"error": "Endpoint not found"}), 404

        limit = request.args.get("limit", 100, type=int)
        limit = min(limit, 500)

        logs = rows_to_list(
            db.execute(
                "SELECT * FROM monitoring_logs WHERE endpoint_id = ? ORDER BY checked_at DESC LIMIT ?",
                (endpoint_id, limit),
            ).fetchall()
        )

        for log in logs:
            log["is_success"] = bool(log["is_success"])

        return jsonify({"logs": logs}), 200
    finally:
        db.close()
