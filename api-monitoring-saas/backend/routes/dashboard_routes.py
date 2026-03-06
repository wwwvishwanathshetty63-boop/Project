import datetime
import logging
from flask import Blueprint, jsonify, g
from backend.models import get_db, row_to_dict, rows_to_list
from backend.utils.auth import token_required

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")


@dashboard_bp.route("/stats", methods=["GET"])
@token_required
def get_stats():
    """Get dashboard statistics for the current user."""
    db = get_db()
    try:
        user_id = g.current_user_id

        endpoints = rows_to_list(
            db.execute("SELECT * FROM api_endpoints WHERE user_id = ?", (user_id,)).fetchall()
        )
        total_apis = len(endpoints)
        active_apis = sum(1 for e in endpoints if e.get("is_active"))

        if total_apis == 0:
            return (
                jsonify(
                    {
                        "stats": {
                            "total_apis": 0,
                            "active_apis": 0,
                            "down_apis": 0,
                            "avg_response_time": 0,
                            "uptime_percentage": 100,
                            "error_rate": 0,
                        },
                        "endpoints": [],
                    }
                ),
                200,
            )

        since = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=24)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        endpoint_ids = [e["id"] for e in endpoints]
        placeholders = ",".join(["?"] * len(endpoint_ids))

        all_logs = rows_to_list(
            db.execute(
                f"SELECT * FROM monitoring_logs WHERE endpoint_id IN ({placeholders}) AND checked_at >= ?",
                (*endpoint_ids, since),
            ).fetchall()
        )

        total_checks = len(all_logs)
        successful_checks = sum(1 for log in all_logs if log.get("is_success"))
        failed_checks = total_checks - successful_checks

        response_times = [log["response_time"] for log in all_logs if log.get("response_time") is not None]
        avg_response_time = round(sum(response_times) / len(response_times), 2) if response_times else 0

        uptime_percentage = round((successful_checks / total_checks) * 100, 2) if total_checks > 0 else 100
        error_rate = round((failed_checks / total_checks) * 100, 2) if total_checks > 0 else 0

        down_apis = 0
        endpoint_statuses = []
        for ep in endpoints:
            latest_log = row_to_dict(
                db.execute(
                    "SELECT * FROM monitoring_logs WHERE endpoint_id = ? ORDER BY checked_at DESC LIMIT 1",
                    (ep["id"],),
                ).fetchone()
            )

            is_down = False
            last_check = None
            last_response_time = None
            last_status_code = None

            if latest_log:
                is_down = not latest_log.get("is_success")
                last_check = latest_log.get("checked_at")
                last_response_time = latest_log.get("response_time")
                last_status_code = latest_log.get("status_code")

            if is_down:
                down_apis += 1

            endpoint_statuses.append(
                {
                    "id": ep["id"],
                    "name": ep["name"],
                    "url": ep["url"],
                    "method": ep["method"],
                    "is_active": bool(ep["is_active"]),
                    "is_down": is_down,
                    "last_check": last_check,
                    "last_response_time": last_response_time,
                    "last_status_code": last_status_code,
                }
            )

        return (
            jsonify(
                {
                    "stats": {
                        "total_apis": total_apis,
                        "active_apis": active_apis,
                        "down_apis": down_apis,
                        "avg_response_time": avg_response_time,
                        "uptime_percentage": uptime_percentage,
                        "error_rate": error_rate,
                    },
                    "endpoints": endpoint_statuses,
                }
            ),
            200,
        )
    except Exception as e:
        logger.error(f"Error fetching dashboard stats: {e}")
        return jsonify({"error": "Failed to load stats. Please try again."}), 500
    finally:
        db.close()


@dashboard_bp.route("/response-times", methods=["GET"])
@token_required
def get_response_times():
    """Get response time data for charts (last 24 hours)."""
    db = get_db()
    try:
        user_id = g.current_user_id

        endpoints = rows_to_list(
            db.execute("SELECT id, name FROM api_endpoints WHERE user_id = ?", (user_id,)).fetchall()
        )

        if not endpoints:
            return jsonify({"series": []}), 200

        since = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=24)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        series = []
        for ep in endpoints:
            logs = rows_to_list(
                db.execute(
                    "SELECT response_time, checked_at, is_success, status_code FROM monitoring_logs WHERE endpoint_id = ? AND checked_at >= ? ORDER BY checked_at ASC",
                    (ep["id"], since),
                ).fetchall()
            )

            data_points = [
                {
                    "time": log["checked_at"],
                    "response_time": log["response_time"],
                    "is_success": bool(log["is_success"]),
                    "status_code": log["status_code"],
                }
                for log in logs
            ]

            series.append({"endpoint_id": ep["id"], "name": ep["name"], "data": data_points})

        return jsonify({"series": series}), 200
    except Exception as e:
        logger.error(f"Error fetching response times: {e}")
        return jsonify({"error": "Failed to load response times. Please try again."}), 500
    finally:
        db.close()
