import os
import sqlite3
import datetime
import sys
from unittest.mock import MagicMock

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.services.monitoring_service import purge_old_data
from backend.config import Config

def test_purging():
    print("Starting purging test...")
    db_path = Config.DATABASE_PATH
    conn = sqlite3.connect(db_path)
    
    try:
        # 1. Insert old data
        old_date = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=35)).strftime("%Y-%m-%d %H:%M:%S")
        recent_date = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
        
        # Mock endpoint for logs
        conn.execute("INSERT OR IGNORE INTO api_endpoints (id, user_id, name, url) VALUES ('test-ep', 'test-user', 'Test', 'http://test.com')")
        
        # Old logs
        conn.execute("INSERT INTO monitoring_logs (endpoint_id, status_code, checked_at) VALUES ('test-ep', 200, ?)", (old_date,))
        conn.execute("INSERT INTO monitoring_logs (endpoint_id, status_code, checked_at) VALUES ('test-ep', 200, ?)", (recent_date,))
        
        # Expired verifications
        expired_verif = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        future_verif = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("INSERT INTO email_verifications (email, otp, expires_at) VALUES ('old@test.com', '123456', ?)", (expired_verif,))
        conn.execute("INSERT INTO email_verifications (email, otp, expires_at) VALUES ('new@test.com', '654321', ?)", (future_verif,))

        # Old invitations
        conn.execute("INSERT INTO employee_invitations (company_id, name, email, token, created_at) VALUES ('test-user', 'Old', 'old@inv.com', 'tok1', ?)", (old_date,))
        conn.execute("INSERT INTO employee_invitations (company_id, name, email, token, created_at) VALUES ('test-user', 'New', 'new@inv.com', 'tok2', ?)", (recent_date,))
        
        conn.commit()
        
        print("Data inserted. Running purge...")
        
        # Force purge by resetting the global timer (mocking if necessary or just waiting if it was 0)
        # In our script, _LAST_PURGE_TIME starts at 0, so it should run once.
        purge_old_data(conn, max_days=30)
        
        # 2. Verify deletions
        logs_count = conn.execute("SELECT COUNT(*) FROM monitoring_logs WHERE endpoint_id = 'test-ep'").fetchone()[0]
        verif_count = conn.execute("SELECT COUNT(*) FROM email_verifications").fetchone()[0]
        inv_count = conn.execute("SELECT COUNT(*) FROM employee_invitations WHERE company_id = 'test-user'").fetchone()[0]
        
        print(f"Results: Logs={logs_count}, Verifications={verif_count}, Invitations={inv_count}")
        
        assert logs_count == 1, f"Expected 1 log, got {logs_count}"
        assert verif_count == 1, f"Expected 1 verification, got {verif_count}"
        assert inv_count == 1, f"Expected 1 invitation, got {inv_count}"
        
        print("✅ Purging test passed!")
        
    finally:
        # Cleanup test data
        conn.execute("DELETE FROM monitoring_logs WHERE endpoint_id = 'test-ep'")
        conn.execute("DELETE FROM api_endpoints WHERE id = 'test-ep'")
        conn.execute("DELETE FROM email_verifications WHERE email IN ('old@test.com', 'new@test.com')")
        conn.execute("DELETE FROM employee_invitations WHERE company_id = 'test-user'")
        conn.commit()
        conn.close()

if __name__ == "__main__":
    test_purging()
