"""TASK 4: Monitoring service with integrated key validation and dynamic status updates."""
import time
import logging
import datetime
import requests as http_requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from backend.config import Config
from backend.models import get_db, row_to_dict, rows_to_list, release_db
from backend.services.alert_service import send_alert_email, build_alert_html, build_key_status_alert_html
from backend.services.api_key_validator import mask_api_key, VALID, INVALID
from backend.services.cache_service import cache

logger = logging.getLogger(__name__)


def check_endpoint(endpoint: dict) -> tuple:
    """
    Send an HTTP request to the endpoint and measure response.
    Returns (log_entry dict, error_detail string).
    """
    url = endpoint["url"]
    method = endpoint.get("method", "GET").upper()
    api_key = endpoint.get("api_key")
    api_key_header = endpoint.get("api_key_header", "Authorization")
    headers = {"User-Agent": "API-Monitor-SaaS/1.0"}

    if api_key:
        headers[api_key_header] = api_key
        logger.debug(f"Attached API Key ({mask_api_key(api_key)}) in header '{api_key_header}'")

    # Set up session with retries for temporary failures
    session = http_requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    session.mount('http://', HTTPAdapter(max_retries=retries))
    session.mount('https://', HTTPAdapter(max_retries=retries))

    api_key_status = "VALID" if api_key else None
    status_code = 0
    is_success = False
    error_detail = None
    start_time = time.time()

    try:
        response = session.request(
            method=method,
            url=url,
            timeout=Config.REQUEST_TIMEOUT_SECONDS,
            allow_redirects=True,
            headers=headers,
        )
        status_code = response.status_code
        is_success = 200 <= status_code < 300

        # Determine API Key Status dynamically based on HTTP response
        if api_key:
            if status_code == 401:
                api_key_status = "INVALID"
                is_success = False
            elif status_code == 403:
                api_key_status = "LIMITED"
                is_success = False
            elif status_code == 429:
                api_key_status = "RATE_LIMITED"
                is_success = False
            elif is_success:
                api_key_status = "VALID"

        if not is_success:
            error_detail = f"HTTP {status_code}"
            if api_key and api_key_status != "VALID":
                error_detail += f" - API Key Failed ({api_key_status})"

    except http_requests.exceptions.Timeout:
        error_detail = "Request timed out"
        if api_key:
            api_key_status = "ERROR"
    except http_requests.exceptions.ConnectionError:
        error_detail = "Connection failed"
        if api_key:
            api_key_status = "ERROR"
    except http_requests.exceptions.RequestException as e:
        error_detail = str(e)[:200]
        if api_key:
            api_key_status = "ERROR"
    finally:
        session.close()

    response_time = round((time.time() - start_time) * 1000, 2)

    log_entry = {
        "endpoint_id": endpoint["id"],
        "status_code": status_code,
        "response_time": response_time,
        "is_success": is_success,
        "api_key_status": api_key_status,
    }

    return log_entry, error_detail


def save_log(log_entry: dict) -> dict:
    """Save a monitoring log entry to the database."""
    db = None
    try:
        db = get_db()
        db.execute(
            "INSERT INTO monitoring_logs (endpoint_id, status_code, response_time, is_success, api_key_status) VALUES (%s, %s, %s, %s, %s)",
            (log_entry["endpoint_id"], log_entry["status_code"], log_entry["response_time"], log_entry["is_success"], log_entry["api_key_status"]),
        )
        db.commit()
        # Invalidate dashboard caches so next request shows fresh data
        cache.invalidate("stats:")
        cache.invalidate("chart:")

        row = db.execute(
            "SELECT * FROM monitoring_logs WHERE endpoint_id = %s ORDER BY checked_at DESC LIMIT 1",
            (log_entry["endpoint_id"],),
        ).fetchone()
        return row_to_dict(row)
    except Exception as e:
        logger.error(f"Failed to save monitoring log: {e}")
        return None
    finally:
        if db:
            release_db(db)


def update_endpoint_key_status(endpoint_id: str, new_status: str):
    """Update the key_status and last_validated_at on the api_endpoints table."""
    db = None
    try:
        db = get_db()
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        db.execute(
            "UPDATE api_endpoints SET key_status = %s, last_validated_at = %s WHERE id = %s",
            (new_status, now, endpoint_id),
        )
        db.commit()
        logger.info(f"Endpoint {endpoint_id} key_status updated to {new_status}")
    except Exception as e:
        logger.error(f"Failed to update endpoint key_status: {e}")
    finally:
        if db:
            release_db(db)


def check_consecutive_failures(endpoint_id: str) -> int:
    """Check how many consecutive failures the endpoint has."""
    db = None
    try:
        db = get_db()
        rows = db.execute(
            "SELECT is_success FROM monitoring_logs WHERE endpoint_id = %s ORDER BY checked_at DESC LIMIT %s",
            (endpoint_id, Config.CONSECUTIVE_FAILURES_THRESHOLD),
        ).fetchall()

        if not rows:
            return 0

        consecutive = 0
        for row in rows:
            if not row["is_success"]:
                consecutive += 1
            else:
                break

        return consecutive
    except Exception as e:
        logger.error(f"Failed to check consecutive failures: {e}")
        return 0
    finally:
        if db:
            release_db(db)


def get_user_email(user_id: str) -> str:
    """Get user's email address."""
    db = None
    try:
        db = get_db()
        row = db.execute("SELECT email FROM users WHERE id = %s", (user_id,)).fetchone()
        return row["email"] if row else None
    except Exception as e:
        logger.error(f"Failed to get user email: {e}")
        return None
    finally:
        if db:
            release_db(db)


# Global variable to track the last time logs were purged
_LAST_PURGE_TIME = 0

def purge_old_data(db, max_days=None):
    """Delete old logs, expired email verifications, and old invitations."""
    global _LAST_PURGE_TIME

    # Only run purge once every 24 hours to reduce load
    current_time = time.time()
    if current_time - _LAST_PURGE_TIME < 86400:
        return

    try:
        if max_days is None:
            max_days = Config.DATA_RETENTION_DAYS

        # 1. Purge Monitoring Logs
        since_logs = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=max_days)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        cursor_logs = db.execute("DELETE FROM monitoring_logs WHERE checked_at < %s", (since_logs,))
        logs_deleted = cursor_logs.rowcount

        # 2. Purge Expired Email Verifications
        now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        cursor_verif = db.execute("DELETE FROM email_verifications WHERE expires_at < %s", (now_str,))
        verif_deleted = cursor_verif.rowcount

        # 3. Purge Old Employee Invitations (e.g., older than 30 days)
        cursor_inv = db.execute("DELETE FROM employee_invitations WHERE created_at < %s", (since_logs,))
        inv_deleted = cursor_inv.rowcount

        db.commit()
        _LAST_PURGE_TIME = current_time

        if logs_deleted > 0 or verif_deleted > 0 or inv_deleted > 0:
            logger.info(
                f"Maintenance Purge: Deleted {logs_deleted} logs, "
                f"{verif_deleted} expired verifications, and {inv_deleted} old invitations."
            )
    except Exception as e:
        logger.error(f"Failed to purge old data: {e}")


def run_monitoring_cycle():
    """
    Main monitoring cycle: check all active endpoints, log results,
    detect key status transitions, and send alerts for failures.
    """
    try:
        db = get_db()

        # Monthly/Daily Cleanup
        purge_old_data(db)

        endpoints = rows_to_list(
            db.execute("SELECT * FROM api_endpoints WHERE is_active = TRUE").fetchall()
        )
        release_db(db)

        if not endpoints:
            logger.debug("No active endpoints to monitor.")
            return

        logger.info(f"Monitoring {len(endpoints)} active endpoints...")

        for endpoint in endpoints:
            try:
                log_entry, error_detail = check_endpoint(endpoint)
                save_log(log_entry)

                # ── TASK 4: Dynamic key_status update ────────
                previous_key_status = endpoint.get("key_status")
                current_key_status = log_entry.get("api_key_status")

                if current_key_status and current_key_status != previous_key_status:
                    update_endpoint_key_status(endpoint["id"], current_key_status)

                    # ── TASK 6: Alert on VALID → INVALID transition ──
                    if previous_key_status == "VALID" and current_key_status == "INVALID":
                        user_email = get_user_email(endpoint["user_id"])
                        if user_email:
                            timestamp = datetime.datetime.now(datetime.timezone.utc).strftime(
                                "%Y-%m-%d %H:%M:%S UTC"
                            )
                            subject = f"🔑 KEY INVALIDATED: {endpoint['name']} API key is now INVALID"
                            html = build_key_status_alert_html(
                                api_name=endpoint["name"],
                                api_url=endpoint["url"],
                                timestamp=timestamp,
                                old_status=previous_key_status,
                                new_status=current_key_status,
                            )
                            send_alert_email(user_email, subject, html)
                            logger.warning(
                                f"Key status alert sent for '{endpoint['name']}': "
                                f"{previous_key_status} → {current_key_status}"
                            )

                if not log_entry["is_success"]:
                    consecutive = check_consecutive_failures(endpoint["id"])
                    user_email = get_user_email(endpoint["user_id"])

                    if user_email:
                        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

                        if current_key_status in ["INVALID", "LIMITED", "RATE_LIMITED"]:
                            alert_type = "failure"
                            subject = f"🔑 API KEY ALERT: {endpoint['name']} is failing due to keys"
                            error_msg = f"Your API Key seems to be {current_key_status}. ({error_detail})"
                        elif consecutive >= Config.CONSECUTIVE_FAILURES_THRESHOLD:
                            alert_type = "consecutive_failures"
                            subject = f"🚨 CRITICAL: {endpoint['name']} — {consecutive} Consecutive Failures"
                            error_msg = f"{error_detail or 'Unknown error'} ({consecutive} consecutive failures)"
                        elif error_detail and "timed out" in error_detail.lower():
                            alert_type = "timeout"
                            subject = f"⏱️ TIMEOUT: {endpoint['name']} is not responding"
                            error_msg = error_detail
                        else:
                            alert_type = "failure"
                            subject = f"⚠️ ALERT: {endpoint['name']} returned error"
                            error_msg = error_detail or f"HTTP {log_entry['status_code']}"

                        html = build_alert_html(
                            api_name=endpoint["name"],
                            api_url=endpoint["url"],
                            timestamp=timestamp,
                            error_details=error_msg,
                            alert_type=alert_type,
                        )
                        send_alert_email(user_email, subject, html)

                        # Also alert company admin if endpoint was created by an employee
                        created_by = endpoint.get("created_by")
                        if created_by and created_by != endpoint["user_id"]:
                            company_email = get_user_email(endpoint["user_id"])
                            if company_email and company_email != user_email:
                                company_subject = f"[Employee Alert] {subject}"
                                company_html = build_alert_html(
                                    api_name=endpoint["name"],
                                    api_url=endpoint["url"],
                                    timestamp=timestamp,
                                    error_details=f"[Added by employee] {error_msg}",
                                    alert_type=alert_type,
                                )
                                send_alert_email(company_email, company_subject, company_html)
                                logger.info(f"Company admin notified about employee endpoint failure: {endpoint['name']}")

                    logger.warning(f"Endpoint '{endpoint['name']}' ({endpoint['url']}) failed: {error_detail}")
                else:
                    logger.info(
                        f"Endpoint '{endpoint['name']}' OK — "
                        f"{log_entry['response_time']}ms, HTTP {log_entry['status_code']}"
                    )

            except Exception as e:
                logger.error(f"Error monitoring endpoint '{endpoint.get('name', 'unknown')}': {e}")

    except Exception as e:
        logger.error(f"Monitoring cycle failed: {e}")


def purge_old_data(db, max_days: int = 30) -> dict:
    """Delete stale monitoring logs, expired OTPs, and old invitations.

    Args:
        db: active database connection
        max_days: logs older than this are deleted (default 30)

    Returns:
        dict with counts of deleted rows per table.
    """
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=max_days)
    cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")

    # Old monitoring logs
    r1 = db.execute(
        "DELETE FROM monitoring_logs WHERE checked_at < %s", (cutoff_str,)
    )
    logs_deleted = getattr(r1, "rowcount", 0) or 0

    # Expired OTPs (already expired — not just old)
    r2 = db.execute(
        "DELETE FROM email_verifications WHERE expires_at < NOW() AND is_used = FALSE"
    )
    otps_deleted = getattr(r2, "rowcount", 0) or 0

    db.commit()
    logger.info(
        f"Data purge complete: {logs_deleted} logs, {otps_deleted} OTPs removed "
        f"(cutoff: {cutoff_str})"
    )
    return {"logs_deleted": logs_deleted, "otps_deleted": otps_deleted}

