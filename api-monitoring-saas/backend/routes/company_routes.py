"""Company-only API routes for monitoring employee activity across all endpoints."""
import datetime
import logging
from flask import Blueprint, jsonify, request, g
from backend.models import get_db, row_to_dict, rows_to_list, release_db
from backend.utils.auth import token_required
from backend.services.cache_service import cache, build_key, TTL_COMPANY_ACTIVITY, TTL_LOGS

logger = logging.getLogger(__name__)

company_bp = Blueprint("company", __name__, url_prefix="/api/company")


def _company_required(func):
    """Decorator that ensures only company-role users can access the endpoint."""
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        if g.current_user_role != "company":
            return jsonify({"error": "Company access required"}), 403
        return func(*args, **kwargs)

    return wrapper


# ── GET /api/company/employees/activity ──────────────────────────────────────

@company_bp.route("/employees/activity", methods=["GET"])
@token_required
@_company_required
def get_employee_activity():
    """Per-employee API stats: endpoint count, down count, key issues, incidents (cached 30s)."""
    company_id = g.current_user_id
    cache_key = build_key("company_activity", company_id)
    cached = cache.get(cache_key)
    if cached:
        return jsonify(cached), 200

    db = get_db()
    try:
        employees = rows_to_list(
            db.execute(
                "SELECT id, name, email, employee_id, created_at FROM users "
                "WHERE company_id = %s AND role = 'employee' ORDER BY name",
                (company_id,),
            ).fetchall()
        )

        since_24h = (
            datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
        ).strftime("%Y-%m-%d %H:%M:%S")

        result_employees = []
        for emp in employees:
            emp_id = emp["id"]

            endpoints = rows_to_list(
                db.execute(
                    "SELECT id, is_active, key_status FROM api_endpoints WHERE created_by = %s",
                    (emp_id,),
                ).fetchall()
            )

            total_endpoints = len(endpoints)
            active_endpoints = sum(1 for e in endpoints if e.get("is_active"))
            key_issues = sum(
                1 for e in endpoints
                if e.get("key_status") in ("INVALID", "LIMITED", "RATE_LIMITED")
            )

            endpoint_ids = [e["id"] for e in endpoints]
            down_endpoints = 0
            recent_incidents = 0
            avg_rt = 0.0
            last_activity = None

            if endpoint_ids:
                ph = ",".join(["%s"] * len(endpoint_ids))

                # Latest check per endpoint (for down count + last_activity)
                latest_rows = db.execute(
                    f"""
                    SELECT l1.endpoint_id, l1.is_success, l1.checked_at
                    FROM monitoring_logs l1
                    JOIN (
                        SELECT endpoint_id, MAX(checked_at) AS max_at
                        FROM monitoring_logs
                        WHERE endpoint_id IN ({ph})
                        GROUP BY endpoint_id
                    ) l2 ON l1.endpoint_id = l2.endpoint_id AND l1.checked_at = l2.max_at
                    """,
                    (*endpoint_ids,),
                ).fetchall()

                for row in latest_rows:
                    if not row["is_success"]:
                        down_endpoints += 1
                    ts = row["checked_at"]
                    if last_activity is None or (ts and ts > last_activity):
                        last_activity = ts

                # Recent 24h stats
                recent_logs = rows_to_list(
                    db.execute(
                        f"SELECT is_success, response_time FROM monitoring_logs "
                        f"WHERE endpoint_id IN ({ph}) AND checked_at >= %s",
                        (*endpoint_ids, since_24h),
                    ).fetchall()
                )

                recent_incidents = sum(1 for l in recent_logs if not l.get("is_success"))
                rts = [l["response_time"] for l in recent_logs if l.get("response_time")]
                avg_rt = round(sum(rts) / len(rts), 2) if rts else 0.0

            result_employees.append(
                {
                    "id": emp_id,
                    "name": emp["name"],
                    "email": emp["email"],
                    "employee_id": emp.get("employee_id"),
                    "joined_at": str(emp.get("created_at", "")),
                    "total_endpoints": total_endpoints,
                    "active_endpoints": active_endpoints,
                    "down_endpoints": down_endpoints,
                    "key_issues": key_issues,
                    "recent_incidents": recent_incidents,
                    "avg_response_time": avg_rt,
                    "last_activity": str(last_activity) if last_activity else None,
                }
            )

        result = {
            "employees": result_employees,
            "total_employees": len(result_employees),
        }
        cache.set(cache_key, result, ttl=TTL_COMPANY_ACTIVITY)
        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error fetching employee activity: {e}")
        return jsonify({"error": "Failed to load employee activity"}), 500
    finally:
        release_db(db)


# ── GET /api/company/employees/<emp_id>/endpoints ─────────────────────────────

@company_bp.route("/employees/<emp_id>/endpoints", methods=["GET"])
@token_required
@_company_required
def get_employee_endpoints(emp_id):
    """All endpoints created by a specific employee (company-only)."""
    company_id = g.current_user_id
    cache_key = build_key("emp_endpoints", company_id, emp_id)
    cached = cache.get(cache_key)
    if cached:
        return jsonify(cached), 200

    db = get_db()
    try:
        # Verify employee belongs to this company
        emp = row_to_dict(
            db.execute(
                "SELECT id, name FROM users WHERE id = %s AND company_id = %s AND role = 'employee'",
                (emp_id, company_id),
            ).fetchone()
        )
        if not emp:
            return jsonify({"error": "Employee not found"}), 404

        endpoints = rows_to_list(
            db.execute(
                "SELECT * FROM api_endpoints WHERE created_by = %s ORDER BY created_at DESC",
                (emp_id,),
            ).fetchall()
        )

        # Attach latest log to each endpoint
        for ep in endpoints:
            ep["is_active"] = bool(ep.get("is_active"))
            # Mask API key
            if ep.get("api_key"):
                key = ep["api_key"]
                ep["api_key_masked"] = key[:6] + "****" + key[-4:] if len(key) > 10 else "****"
                ep["api_key"] = None

            latest = row_to_dict(
                db.execute(
                    "SELECT is_success, response_time, status_code, checked_at "
                    "FROM monitoring_logs WHERE endpoint_id = %s ORDER BY checked_at DESC LIMIT 1",
                    (ep["id"],),
                ).fetchone()
            )
            if latest:
                ep["is_down"] = not bool(latest.get("is_success"))
                ep["last_check"] = latest.get("checked_at")
                ep["last_response_time"] = latest.get("response_time")
                ep["last_status_code"] = latest.get("status_code")
            else:
                ep["is_down"] = False
                ep["last_check"] = None
                ep["last_response_time"] = None
                ep["last_status_code"] = None

        result = {
            "employee": {"id": emp["id"], "name": emp["name"]},
            "endpoints": endpoints,
        }
        cache.set(cache_key, result, ttl=20)
        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error fetching employee endpoints: {e}")
        return jsonify({"error": "Failed to load employee endpoints"}), 500
    finally:
        release_db(db)


# ── GET /api/company/employees/<emp_id>/logs ──────────────────────────────────

@company_bp.route("/employees/<emp_id>/logs", methods=["GET"])
@token_required
@_company_required
def get_employee_logs(emp_id):
    """Monitoring logs for all endpoints owned by a specific employee."""
    company_id = g.current_user_id
    limit = min(request.args.get("limit", 50, type=int), 500)
    cache_key = build_key("emp_logs", company_id, emp_id, limit)
    cached = cache.get(cache_key)
    if cached:
        return jsonify(cached), 200

    db = get_db()
    try:
        # Verify employee belongs to company
        emp = row_to_dict(
            db.execute(
                "SELECT id, name FROM users WHERE id = %s AND company_id = %s AND role = 'employee'",
                (emp_id, company_id),
            ).fetchone()
        )
        if not emp:
            return jsonify({"error": "Employee not found"}), 404

        endpoint_ids = [
            r["id"]
            for r in db.execute(
                "SELECT id FROM api_endpoints WHERE created_by = %s", (emp_id,)
            ).fetchall()
        ]

        logs = []
        if endpoint_ids:
            ph = ",".join(["%s"] * len(endpoint_ids))
            ep_names = {
                r["id"]: r["name"]
                for r in db.execute(
                    f"SELECT id, name FROM api_endpoints WHERE id IN ({ph})", (*endpoint_ids,)
                ).fetchall()
            }
            raw_logs = rows_to_list(
                db.execute(
                    f"SELECT * FROM monitoring_logs WHERE endpoint_id IN ({ph}) "
                    f"ORDER BY checked_at DESC LIMIT %s",
                    (*endpoint_ids, limit),
                ).fetchall()
            )
            for log in raw_logs:
                log["is_success"] = bool(log.get("is_success"))
                log["endpoint_name"] = ep_names.get(log.get("endpoint_id"), "Unknown")
                logs.append(log)

        result = {
            "employee": {"id": emp["id"], "name": emp["name"]},
            "logs": logs,
        }
        cache.set(cache_key, result, ttl=TTL_LOGS)
        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error fetching employee logs: {e}")
        return jsonify({"error": "Failed to load employee logs"}), 500
    finally:
        release_db(db)
