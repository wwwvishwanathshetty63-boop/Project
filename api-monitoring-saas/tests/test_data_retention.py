"""
Test Suite: Data retention / log purge (Supabase/PostgreSQL version).
Verifies that old monitoring logs and expired OTPs are purged correctly.
"""
import datetime
import pytest
from backend.models import get_db, release_db
from backend.services.monitoring_service import purge_old_data


def _dt(days_ago=0, hours_ago=0, future_hours=0):
    base = datetime.datetime.utcnow()
    delta = datetime.timedelta(days=days_ago, hours=hours_ago)
    if future_hours:
        return (base + datetime.timedelta(hours=future_hours)).strftime("%Y-%m-%d %H:%M:%S")
    return (base - delta).strftime("%Y-%m-%d %H:%M:%S")


@pytest.fixture(scope="module")
def db_conn():
    db = get_db()
    yield db
    release_db(db)


def test_purging(db_conn):
    """Insert old and recent records, run purge, verify only old ones removed."""
    db = db_conn
    ep_id   = "test-purge-ep-001"
    user_id = "test-purge-user-001"

    try:
        # --- Setup ---
        # Ensure test user exists
        db.execute(
            "INSERT INTO users (id, name, email, password_hash, role) "
            "VALUES (%s, 'Purge Test User', %s, %s, 'company') ON CONFLICT (id) DO NOTHING",
            (user_id, "test-purge@example.com", "hash"),
        )
        # Ensure test endpoint exists (PostgreSQL uses ON CONFLICT)
        db.execute(
            "INSERT INTO api_endpoints (id, user_id, name, url) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
            (ep_id, user_id, "Purge Test", "http://purge-test.example.com"),
        )

        old_ts    = _dt(days_ago=35)
        recent_ts = _dt(days_ago=5)

        # Old log (>30 days) — should be purged
        db.execute(
            "INSERT INTO monitoring_logs (endpoint_id, status_code, response_time, is_success, checked_at) "
            "VALUES (%s, %s, %s, %s, %s)",
            (ep_id, 200, 120.0, True, old_ts),
        )
        # Recent log — should survive
        db.execute(
            "INSERT INTO monitoring_logs (endpoint_id, status_code, response_time, is_success, checked_at) "
            "VALUES (%s, %s, %s, %s, %s)",
            (ep_id, 200, 95.0, True, recent_ts),
        )

        # Expired OTP — should be purged
        db.execute(
            "INSERT INTO email_verifications (email, otp, expires_at) VALUES (%s, %s, %s)",
            ("purge-old@test.com", "111111", _dt(hours_ago=2)),
        )
        # Valid OTP — should survive
        db.execute(
            "INSERT INTO email_verifications (email, otp, expires_at) VALUES (%s, %s, %s)",
            ("purge-new@test.com", "222222", _dt(future_hours=2)),
        )
        db.commit()

        # --- Act ---
        purge_old_data(db, max_days=30)

        # --- Assert ---
        logs = db.execute(
            "SELECT COUNT(*) as count FROM monitoring_logs WHERE endpoint_id = %s", (ep_id,)
        ).fetchone()["count"]
        assert logs == 1, f"Expected 1 recent log to survive, got {logs}"

        old_otp = db.execute(
            "SELECT COUNT(*) as count FROM email_verifications WHERE email = 'purge-old@test.com'"
        ).fetchone()["count"]
        assert old_otp == 0, "Expired OTP should have been purged"

        new_otp = db.execute(
            "SELECT COUNT(*) as count FROM email_verifications WHERE email = 'purge-new@test.com'"
        ).fetchone()["count"]
        assert new_otp == 1, "Valid OTP should survive purge"

    finally:
        # Cleanup
        db.execute("DELETE FROM monitoring_logs WHERE endpoint_id = %s", (ep_id,))
        db.execute("DELETE FROM api_endpoints WHERE id = %s", (ep_id,))
        db.execute("DELETE FROM email_verifications WHERE email IN ('purge-old@test.com', 'purge-new@test.com')")
        db.commit()
