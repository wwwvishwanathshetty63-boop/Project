import time
import logging
import datetime
import requests as http_requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from backend.config import Config
from backend.models import get_db, row_to_dict, rows_to_list, release_db
from backend.services.alert_service import send_alert_email, build_alert_html

logger = logging.getLogger(__name__)

def mask_api_key(key: str) -> str:
    """Masks an API key for safe logging."""
    if not key:
        return ""
    if len(key) <= 8:
        return "********"
    return f"{key[:4]}{'*' * (len(key) - 8)}{key[-4:]}"
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
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[ 500, 502, 503, 504 ])
    session.mount('http://', HTTPAdapter(max_retries=retries))
    session.mount('https://', HTTPAdapter(max_retries=retries))

    api_key_status = "Valid" if api_key else None

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
                api_key_status = "Invalid/Dummy"
                is_success = False
            elif status_code == 403:
                api_key_status = "Forbidden (Insufficient Perms)"
                is_success = False
            elif status_code == 429:
                api_key_status = "Rate Limited"
                is_success = False
            elif is_success:
                api_key_status = "Valid"

        if not is_success:
            error_detail = f"HTTP {status_code}"
            if api_key and api_key_status != "Valid":
                 error_detail += f" - API Key Failed ({api_key_status})"

    except http_requests.exceptions.Timeout:
        error_detail = "Request timed out"
        if api_key: api_key_status = "Error"
    except http_requests.exceptions.ConnectionError:
        error_detail = "Connection failed"
        if api_key: api_key_status = "Error"
    except http_requests.exceptions.RequestException as e:
        error_detail = str(e)[:200]
        if api_key: api_key_status = "Error"
    finally:
        session.close()

    response_time = round((time.time() - start_time) * 1000, 2)

    log_entry = {
        "endpoint_id": endpoint["id"],
        "status_code": status_code,
        "response_time": response_time,
        "is_success": 1 if is_success else 0,
        "api_key_status": api_key_status
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
    and send alerts for failures.
    """
    try:
        db = get_db()
        
        # Monthly/Daily Cleanup
        purge_old_data(db)

        endpoints = rows_to_list(
            db.execute("SELECT * FROM api_endpoints WHERE is_active = 1").fetchall()
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

                if not log_entry["is_success"]:
                    consecutive = check_consecutive_failures(endpoint["id"])
                    user_email = get_user_email(endpoint["user_id"])

                    if user_email:
                        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

                        if log_entry.get("api_key_status") in ["Invalid/Dummy", "Forbidden (Insufficient Perms)", "Rate Limited"]:
                            alert_type = "failure"
                            subject = f"🔑 API KEY ALERT: {endpoint['name']} is failing due to keys"
                            error_msg = f"Your API Key seems to be {log_entry['api_key_status']}. ({error_detail})"
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
