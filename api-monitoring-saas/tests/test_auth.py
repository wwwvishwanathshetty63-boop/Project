"""
Test Suite 1: Authentication, roles, and JWT enforcement.
Covers: login, bad credentials, role guards, employee access control.
"""
import pytest
from tests.conftest import register_and_login, register_employee, auth_header

COMPANY_EMAIL = "test_company_auth@example.com"
COMPANY_PASS  = "TestPass@123"


@pytest.fixture(scope="module")
def company_token(client):
    return register_and_login(client, COMPANY_EMAIL, COMPANY_PASS, "Auth Test Co")


@pytest.fixture(scope="module")
def employee_token(client, company_token):
    return register_employee(client, company_token, "Emp Auth", "emp_auth@example.com")


class TestAuthentication:

    def test_login_success(self, client, company_token):
        """Valid credentials return a JWT token and user info."""
        assert company_token is not None and len(company_token) > 10

    def test_login_wrong_password(self, client):
        res = client.post("/api/auth/login", json={"email": COMPANY_EMAIL, "password": "WrongPass@999"})
        assert res.status_code == 401
        assert "error" in res.get_json()

    def test_login_nonexistent_email(self, client):
        res = client.post("/api/auth/login", json={"email": "nobody@nowhere.com", "password": "Any@Pass1"})
        assert res.status_code in (401, 404)

    def test_login_missing_fields(self, client):
        res = client.post("/api/auth/login", json={})
        assert res.status_code == 400

    def test_protected_route_no_token(self, client):
        """Routes requiring auth must reject requests without a token."""
        res = client.get("/api/endpoints")
        assert res.status_code == 401

    def test_protected_route_invalid_token(self, client):
        res = client.get("/api/endpoints", headers={"Authorization": "Bearer faketoken123"})
        assert res.status_code == 401

    def test_protected_route_malformed_header(self, client):
        res = client.get("/api/endpoints", headers={"Authorization": "NotBearer token"})
        assert res.status_code == 401

    def test_company_can_access_analytics(self, client, company_token):
        res = client.get("/api/dashboard/analytics", headers=auth_header(company_token))
        assert res.status_code == 200

    def test_employee_cannot_access_analytics(self, client, employee_token):
        """Analytics is company-only; employees must get 403."""
        res = client.get("/api/dashboard/analytics", headers=auth_header(employee_token))
        assert res.status_code == 403

    def test_employee_cannot_access_company_routes(self, client, employee_token):
        res = client.get("/api/company/employees/activity", headers=auth_header(employee_token))
        assert res.status_code == 403

    def test_company_can_access_company_routes(self, client, company_token):
        res = client.get("/api/company/employees/activity", headers=auth_header(company_token))
        assert res.status_code == 200

    def test_profile_returns_correct_role(self, client, company_token):
        res = client.get("/api/auth/profile", headers=auth_header(company_token))
        data = res.get_json()
        assert res.status_code == 200
        # Profile is nested under 'user' key
        user = data.get("user", data)  # handle both {user:{...}} and flat
        role = user.get("role") if isinstance(user, dict) else data.get("role")
        assert role == "company"

    def test_employee_profile_returns_employee_role(self, client, employee_token):
        res = client.get("/api/auth/profile", headers=auth_header(employee_token))
        data = res.get_json()
        assert res.status_code == 200
        user = data.get("user", data)
        role = user.get("role") if isinstance(user, dict) else data.get("role")
        assert role == "employee"
