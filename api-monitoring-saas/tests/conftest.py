"""Shared fixtures and helpers for the API Monitoring SaaS test suite."""
import sys, os, time, threading
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from backend.app import create_app

# ── Flask test client ────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def app():
    app = create_app()
    app.config["TESTING"] = True
    return app

@pytest.fixture(scope="session")
def client(app):
    return app.test_client()

# ── Auth helpers ─────────────────────────────────────────────────────────────

def register_and_login(client, email, password, name="Test Company"):
    """Register a company account (direct DB insert) and return token."""
    import bcrypt, uuid
    from backend.models import get_db, release_db
    db = get_db()
    try:
        user_id = uuid.uuid4().hex
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        db.execute(
            "INSERT INTO users (id, email, password_hash, name, role) "
            "VALUES (%s, %s, %s, %s, 'company') ON CONFLICT (email) DO UPDATE "
            "SET password_hash = EXCLUDED.password_hash",
            (user_id, email, pw_hash, name),
        )
        db.commit()
    finally:
        release_db(db)

    res = client.post("/api/auth/login",
                      json={"email": email, "password": password, "login_type": "company"})
    assert res.status_code == 200, f"Company login failed: {res.get_json()}"
    return res.get_json()["token"]


def register_employee(client, company_token, name, base_email):
    """Invite employee via API and log them in. Returns token."""
    import uuid
    # Ensure email is unique across test runs
    email = f"emp_{uuid.uuid4().hex[:8]}@{base_email.split('@')[-1]}"
    res = client.post(
        "/api/auth/invite-employee",
        json={"name": name, "email": email},
        headers={"Authorization": f"Bearer {company_token}"},
    )
    data = res.get_json()
    assert res.status_code == 201, f"Invite failed: {data}"
    # dev_password is returned when SMTP skips delivery (test domains)
    raw_pw = data.get("dev_password")
    assert raw_pw, f"No dev_password in invite response: {data}"

    login = client.post(
        "/api/auth/login",
        json={"email": email, "password": raw_pw, "name": name, "login_type": "employee"},
    )
    assert login.status_code == 200, f"Employee login failed: {login.get_json()}"
    return login.get_json()["token"]


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


# ── Mock HTTP Server ─────────────────────────────────────────────────────────
from http.server import HTTPServer, BaseHTTPRequestHandler

class _MockAPIHandler(BaseHTTPRequestHandler):
    scenario = "ok"
    request_count = 0
    degrade_count = 0  # isolated counter for degradation tests
    degradation_mode = False

    def log_message(self, *_): pass

    def do_GET(self):
        _MockAPIHandler.request_count += 1
        cnt = _MockAPIHandler.request_count
        path = self.path

        if path == "/ok":
            self._send(200, {"status": "ok", "request": cnt})
        elif path == "/slow":
            # 200ms base + 100ms per request when in degradation_mode
            _MockAPIHandler.degrade_count += 1
            delay = (0.2 + _MockAPIHandler.degrade_count * 0.1) if _MockAPIHandler.degradation_mode else 0.2
            delay = min(delay, 4.0)
            time.sleep(delay)
            self._send(200, {"status": "slow", "delay_ms": int(delay * 1000)})
        elif path == "/very-slow":
            time.sleep(6)
            self._send(200, {"status": "very_slow"})
        elif path == "/down":
            self._send(500, {"error": "Internal Server Error"})
        elif path == "/rate-limit":
            self._send(429, {"error": "Too Many Requests"})
        elif path == "/unauthorized":
            self._send(401, {"error": "Invalid API key"})
        elif path == "/forbidden":
            self._send(403, {"error": "Access forbidden"})
        elif path == "/__admin__/degrade_on":
            _MockAPIHandler.degradation_mode = True
            self._send(200, {"status": "degradation_on"})
        elif path == "/__admin__/degrade_off":
            _MockAPIHandler.degradation_mode = False
            self._send(200, {"status": "degradation_off"})
        elif path == "/__admin__/reset":
            _MockAPIHandler.request_count = 0
            _MockAPIHandler.degrade_count = 0
            _MockAPIHandler.degradation_mode = False
            self._send(200, {"status": "reset"})
        elif path == "/unstable":
            # Every 3rd call is down — but use 404 (not retried) to avoid retry interference
            if cnt % 3 == 0:
                self._send(404, {"error": "Not Found"})
            else:
                self._send(200, {"status": "ok"})
        elif path == "/key-check":
            key = self.headers.get("Authorization", "")
            if key == "Bearer valid-key-123":
                self._send(200, {"auth": "ok"})
            else:
                self._send(401, {"error": "Bad key"})
        else:
            self._send(404, {"error": "Not found"})

    def _send(self, code, body):
        import json
        payload = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


_mock_server_instance = None
MOCK_PORT = 19876

def start_mock_server():
    global _mock_server_instance
    if _mock_server_instance:
        return
    server = HTTPServer(("127.0.0.1", MOCK_PORT), _MockAPIHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    _mock_server_instance = server
    time.sleep(0.3)

def mock_url(path):
    return f"http://127.0.0.1:{MOCK_PORT}{path}"

def reset_mock_counter():
    import requests
    try:
        requests.get(f"http://127.0.0.1:{MOCK_PORT}/__admin__/reset", timeout=1)
    except:
        pass

def set_degradation_mode(mode: bool):
    import requests
    endpoint = "degrade_on" if mode else "degrade_off"
    try:
        requests.get(f"http://127.0.0.1:{MOCK_PORT}/__admin__/{endpoint}", timeout=1)
    except:
        pass
