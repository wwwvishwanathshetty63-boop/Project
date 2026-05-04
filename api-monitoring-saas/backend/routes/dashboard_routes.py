import datetime
import logging
from flask import Blueprint, jsonify, request, g
from backend.models import get_db, row_to_dict, rows_to_list, release_db, release_db
from backend.utils.auth import token_required
from backend.services.cache_service import cache, build_key, TTL_STATS, TTL_CHART, TTL_ANALYTICS

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")


@dashboard_bp.route("/stats", methods=["GET"])
@token_required
def get_stats():
    """Dashboard stats — employees see only their own endpoints, company sees all (cached 20s)."""
    user_id = g.current_user_id
    user_role = g.current_user_role
    time_range = request.args.get("range", "1d")

    cache_key = build_key("stats", user_id, time_range)
    cached = cache.get(cache_key)
    if cached:
        return jsonify(cached), 200

    db = get_db()
    try:
        days_map = {"1d": 1, "7d": 7, "30d": 30}
        days = days_map.get(time_range, 1)

        # Employees → only endpoints they created; Company → all owned endpoints
        if user_role == "employee":
            endpoints = rows_to_list(
                db.execute("SELECT * FROM api_endpoints WHERE created_by = %s", (user_id,)).fetchall()
            )
        else:
            endpoints = rows_to_list(
                db.execute("SELECT * FROM api_endpoints WHERE user_id = %s", (user_id,)).fetchall()
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

        since = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        endpoint_ids = [e["id"] for e in endpoints]
        placeholders = ",".join(["%s"] * len(endpoint_ids))

        all_logs = rows_to_list(
            db.execute(
                f"SELECT * FROM monitoring_logs WHERE endpoint_id IN ({placeholders}) AND checked_at >= %s",
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
                    "SELECT * FROM monitoring_logs WHERE endpoint_id = %s ORDER BY checked_at DESC LIMIT 1",
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

        result = {
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
        cache.set(cache_key, result, ttl=TTL_STATS)
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error fetching dashboard stats: {e}")
        return jsonify({"error": "Failed to load stats. Please try again."}), 500
    finally:
        release_db(db)


@dashboard_bp.route("/response-times", methods=["GET"])
@token_required
def get_response_times():
    """Response time chart data — supports from_time/to_time (ISO UTC) or range param."""
    user_id = g.current_user_id
    user_role = g.current_user_role

    # Custom time window takes priority over range
    from_time = request.args.get("from_time")
    to_time   = request.args.get("to_time")

    if from_time and to_time:
        try:
            since_dt = datetime.datetime.fromisoformat(from_time.replace('Z', '+00:00'))
            until_dt = datetime.datetime.fromisoformat(to_time.replace('Z', '+00:00'))
            since  = since_dt.strftime("%Y-%m-%d %H:%M:%S")
            until  = until_dt.strftime("%Y-%m-%d %H:%M:%S")
            cache_key = build_key("chart", user_id, from_time, to_time)
        except Exception:
            return jsonify({"error": "Invalid from_time/to_time format (use ISO 8601)"}), 400
        use_until = True
    else:
        time_range = request.args.get("range", "1d")
        days_map = {"1h": 1/24, "1d": 1, "7d": 7, "30d": 30}
        days = days_map.get(time_range, 1)
        since = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        until = None
        cache_key = build_key("chart", user_id, time_range)
        use_until = False

    cached = cache.get(cache_key)
    if cached:
        return jsonify(cached), 200

    db = get_db()
    try:
        if user_role == "employee":
            endpoints = rows_to_list(
                db.execute("SELECT id, name FROM api_endpoints WHERE created_by = %s", (user_id,)).fetchall()
            )
        else:
            endpoints = rows_to_list(
                db.execute("SELECT id, name FROM api_endpoints WHERE user_id = %s", (user_id,)).fetchall()
            )

        if not endpoints:
            return jsonify({"series": []}), 200

        series = []
        for ep in endpoints:
            if use_until:
                logs = rows_to_list(
                    db.execute(
                        "SELECT response_time, checked_at, is_success, status_code FROM monitoring_logs WHERE endpoint_id = %s AND checked_at >= %s AND checked_at <= %s ORDER BY checked_at ASC",
                        (ep["id"], since, until),
                    ).fetchall()
                )
            else:
                logs = rows_to_list(
                    db.execute(
                        "SELECT response_time, checked_at, is_success, status_code FROM monitoring_logs WHERE endpoint_id = %s AND checked_at >= %s ORDER BY checked_at ASC",
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

        result = {"series": series}
        cache.set(cache_key, result, ttl=TTL_CHART)
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error fetching response times: {e}")
        return jsonify({"error": "Failed to load response times. Please try again."}), 500
    finally:
        release_db(db)



@dashboard_bp.route("/analytics", methods=["GET"])
@token_required
def get_analytics():
    """Get real-time analytics data for the Company dashboard (cached 30s)."""
    if g.current_user_role != "company":
        return jsonify({"error": "Only company accounts can view analytics"}), 403

    user_id = g.current_user_id
    cache_key = build_key("analytics", user_id)
    cached = cache.get(cache_key)
    if cached:
        return jsonify(cached), 200

    db = get_db()
    try:

        # Get all endpoints for company
        endpoints = rows_to_list(
            db.execute("SELECT * FROM api_endpoints WHERE user_id = %s", (user_id,)).fetchall()
        )

        total_apis = len(endpoints)
        if total_apis == 0:
            return jsonify({
                "total_apis": 0,
                "total_checks_today": 0,
                "successful_today": 0,
                "failed_today": 0,
                "avg_response_time": 0,
                "uptime_percentage": 100,
                "error_rate": 0,
                "down_apis": 0,
                "hourly_data": [],
                "incidents": [],
                "employees": [],
            }), 200

        # Today's data
        today_start = datetime.datetime.now(datetime.timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ).strftime("%Y-%m-%d %H:%M:%S")

        endpoint_ids = [e["id"] for e in endpoints]
        placeholders = ",".join(["%s"] * len(endpoint_ids))

        # Today's logs
        today_logs = rows_to_list(
            db.execute(
                f"SELECT * FROM monitoring_logs WHERE endpoint_id IN ({placeholders}) AND checked_at >= %s",
                (*endpoint_ids, today_start),
            ).fetchall()
        )

        total_checks_today = len(today_logs)
        successful_today = sum(1 for log in today_logs if log.get("is_success"))
        failed_today = total_checks_today - successful_today

        response_times = [log["response_time"] for log in today_logs if log.get("response_time") is not None]
        avg_response_time = round(sum(response_times) / len(response_times), 2) if response_times else 0

        uptime_pct = round((successful_today / total_checks_today) * 100, 2) if total_checks_today > 0 else 100
        error_rate = round((failed_today / total_checks_today) * 100, 2) if total_checks_today > 0 else 0

        # Down APIs
        down_apis = 0
        for ep in endpoints:
            latest = row_to_dict(
                db.execute(
                    "SELECT is_success FROM monitoring_logs WHERE endpoint_id = %s ORDER BY checked_at DESC LIMIT 1",
                    (ep["id"],),
                ).fetchone()
            )
            if latest and not latest.get("is_success"):
                down_apis += 1

        # Hourly breakdown for chart
        hourly_data = []
        for hour in range(24):
            hour_start = datetime.datetime.now(datetime.timezone.utc).replace(
                hour=hour, minute=0, second=0, microsecond=0
            )
            hour_end = hour_start + datetime.timedelta(hours=1)
            hour_logs = [
                log for log in today_logs
                if log.get("checked_at") and (
                    (isinstance(log["checked_at"], str) and hour_start.strftime("%Y-%m-%d %H:%M:%S") <= log["checked_at"] < hour_end.strftime("%Y-%m-%d %H:%M:%S"))
                    or (hasattr(log["checked_at"], 'replace') and hour_start <= log["checked_at"].replace(tzinfo=datetime.timezone.utc) < hour_end)
                )
            ]
            hour_rts = [log["response_time"] for log in hour_logs if log.get("response_time") is not None]
            hourly_data.append({
                "hour": f"{hour:02d}:00",
                "checks": len(hour_logs),
                "avg_response_time": round(sum(hour_rts) / len(hour_rts), 2) if hour_rts else 0,
                "failures": sum(1 for log in hour_logs if not log.get("is_success")),
            })

        # Incidents (failed checks today)
        incidents = []
        failed_logs = [log for log in today_logs if not log.get("is_success")]
        ep_map = {e["id"]: e["name"] for e in endpoints}
        for log in failed_logs[-20:]:  # Last 20 incidents
            incidents.append({
                "name": ep_map.get(log["endpoint_id"], "Unknown"),
                "error": f"HTTP {log.get('status_code', 0)}" if log.get("status_code") else "Connection failed",
                "time": log.get("checked_at", ""),
                "response_time": log.get("response_time"),
            })

        # Employees under this company
        employees = rows_to_list(
            db.execute(
                "SELECT id, name, email, employee_id, created_at FROM users WHERE company_id = %s AND role = 'employee'",
                (user_id,),
            ).fetchall()
        )

        analytics_result = {
            "total_apis": total_apis,
            "total_checks_today": total_checks_today,
            "successful_today": successful_today,
            "failed_today": failed_today,
            "avg_response_time": avg_response_time,
            "uptime_percentage": uptime_pct,
            "error_rate": error_rate,
            "down_apis": down_apis,
            "hourly_data": hourly_data,
            "incidents": incidents,
            "employees": employees,
        }
        cache.set(cache_key, analytics_result, ttl=TTL_ANALYTICS)
        return jsonify(analytics_result), 200

    except Exception as e:
        logger.error(f"Error fetching analytics: {e}")
        return jsonify({"error": "Failed to load analytics"}), 500
    finally:
        release_db(db)


@dashboard_bp.route("/send-daily-report", methods=["POST"])
@token_required
def send_daily_report():
    """Manually trigger a daily summary email to the company admin."""
    if g.current_user_role != "company":
        return jsonify({"error": "Only company accounts can send reports"}), 403

    db = get_db()
    try:
        user_id = g.current_user_id
        user = row_to_dict(db.execute("SELECT email, name FROM users WHERE id = %s", (user_id,)).fetchone())
        if not user:
            return jsonify({"error": "User not found"}), 404

        # Get today's data
        endpoints = rows_to_list(
            db.execute("SELECT * FROM api_endpoints WHERE user_id = %s", (user_id,)).fetchall()
        )

        today_start = datetime.datetime.now(datetime.timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ).strftime("%Y-%m-%d %H:%M:%S")

        endpoint_ids = [e["id"] for e in endpoints]
        total_checks = 0
        successful = 0
        failed = 0
        all_rts = []
        incidents = []
        down_count = 0

        if endpoint_ids:
            placeholders = ",".join(["%s"] * len(endpoint_ids))
            logs = rows_to_list(
                db.execute(
                    f"SELECT * FROM monitoring_logs WHERE endpoint_id IN ({placeholders}) AND checked_at >= %s",
                    (*endpoint_ids, today_start),
                ).fetchall()
            )
            ep_map = {e["id"]: e["name"] for e in endpoints}

            total_checks = len(logs)
            successful = sum(1 for l in logs if l.get("is_success"))
            failed = total_checks - successful
            all_rts = [l["response_time"] for l in logs if l.get("response_time") is not None]

            for l in logs:
                if not l.get("is_success"):
                    incidents.append({
                        "name": ep_map.get(l["endpoint_id"], "Unknown"),
                        "error": f"HTTP {l.get('status_code', 0)}",
                        "time": l.get("checked_at", ""),
                    })

            for ep in endpoints:
                latest = row_to_dict(
                    db.execute(
                        "SELECT is_success FROM monitoring_logs WHERE endpoint_id = %s ORDER BY checked_at DESC LIMIT 1",
                        (ep["id"],),
                    ).fetchone()
                )
                if latest and not latest.get("is_success"):
                    down_count += 1

        avg_rt = round(sum(all_rts) / len(all_rts), 2) if all_rts else 0
        uptime = round((successful / total_checks) * 100, 2) if total_checks > 0 else 100

        summary_data = {
            "total_checks": total_checks,
            "successful_checks": successful,
            "failed_checks": failed,
            "avg_response_time": avg_rt,
            "uptime_percentage": uptime,
            "total_apis": len(endpoints),
            "down_apis": down_count,
            "incidents": incidents[:10],
            "date": datetime.datetime.now(datetime.timezone.utc).strftime("%B %d, %Y"),
        }

        from backend.services.alert_service import send_daily_summary_email
        email_sent = send_daily_summary_email(user["email"], summary_data)

        return jsonify({
            "message": "Daily report sent!" if email_sent else "Report generated (SMTP not configured)",
            "email_sent": email_sent,
            "summary": summary_data,
        }), 200

    except Exception as e:
        logger.error(f"Error sending daily report: {e}")
        return jsonify({"error": "Failed to send daily report"}), 500
    finally:
        release_db(db)
