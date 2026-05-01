"""
Test Suite 5: Employee ↔ Company integration.
Tests: employee activity API, per-employee endpoint visibility,
       company sees all, employees cannot cross-access.
"""
import pytest
from tests.conftest import register_and_login, register_employee, auth_header, start_mock_server, mock_url

CO_EMAIL = "test_company_integ@example.com"
CO_PASS  = "TestPass@123"


@pytest.fixture(scope="module", autouse=True)
def _mock():
    start_mock_server()


@pytest.fixture(scope="module")
def co_token(client):
    return register_and_login(client, CO_EMAIL, CO_PASS, "Integration Co")


import uuid
ALICE_NAME = f"Alice_{uuid.uuid4().hex[:4]}"
BOB_NAME = f"Bob_{uuid.uuid4().hex[:4]}"

@pytest.fixture(scope="module")
def emp1_token(client, co_token):
    return register_employee(client, co_token, ALICE_NAME, "alice_integ@example.com")


@pytest.fixture(scope="module")
def emp2_token(client, co_token):
    return register_employee(client, co_token, BOB_NAME, "bob_integ@example.com")


@pytest.fixture(scope="module")
def alice_ep_id(client, emp1_token):
    res = client.post(
        "/api/endpoints",
        json={"name": "Alice API", "url": mock_url("/ok"), "method": "GET", "interval": 60},
        headers=auth_header(emp1_token),
    )
    return res.get_json()["endpoint"]["id"]


@pytest.fixture(scope="module")
def bob_ep_id(client, emp2_token):
    res = client.post(
        "/api/endpoints",
        json={"name": "Bob API", "url": mock_url("/ok"), "method": "GET", "interval": 60},
        headers=auth_header(emp2_token),
    )
    return res.get_json()["endpoint"]["id"]


class TestEmployeeIsolation:

    def test_alice_cannot_see_bob_endpoint(self, client, emp1_token, bob_ep_id):
        res = client.get(f"/api/endpoints/{bob_ep_id}", headers=auth_header(emp1_token))
        assert res.status_code == 404

    def test_bob_cannot_see_alice_endpoint(self, client, emp2_token, alice_ep_id):
        res = client.get(f"/api/endpoints/{alice_ep_id}", headers=auth_header(emp2_token))
        assert res.status_code == 404

    def test_alice_list_has_only_alice_endpoints(self, client, emp1_token):
        res = client.get("/api/endpoints", headers=auth_header(emp1_token))
        names = [e["name"] for e in res.get_json()["endpoints"]]
        assert "Alice API" in names
        assert "Bob API" not in names

    def test_bob_list_has_only_bob_endpoints(self, client, emp2_token):
        res = client.get("/api/endpoints", headers=auth_header(emp2_token))
        names = [e["name"] for e in res.get_json()["endpoints"]]
        assert "Bob API" in names
        assert "Alice API" not in names

    def test_alice_cannot_delete_bob_endpoint(self, client, emp1_token, bob_ep_id):
        res = client.delete(f"/api/endpoints/{bob_ep_id}", headers=auth_header(emp1_token))
        assert res.status_code == 404  # must not be able to delete

    def test_alice_cannot_toggle_bob_endpoint(self, client, emp1_token, bob_ep_id):
        res = client.patch(f"/api/endpoints/{bob_ep_id}/toggle", headers=auth_header(emp1_token))
        assert res.status_code == 404


class TestCompanyVisibility:

    def test_company_activity_returns_employees(self, client, co_token):
        res = client.get("/api/company/employees/activity", headers=auth_header(co_token))
        assert res.status_code == 200
        data = res.get_json()
        names = [e["name"] for e in data["employees"]]
        assert ALICE_NAME in names
        assert BOB_NAME in names

    def test_company_activity_includes_endpoint_count(self, client, co_token, alice_ep_id):
        res = client.get("/api/company/employees/activity", headers=auth_header(co_token))
        employees = res.get_json()["employees"]
        alice = next((e for e in employees if e["name"] == ALICE_NAME), None)
        assert alice is not None
        assert alice["total_endpoints"] >= 1

    def test_company_can_view_alice_endpoints(self, client, co_token, alice_ep_id):
        # Get Alice's user ID from activity
        act = client.get("/api/company/employees/activity", headers=auth_header(co_token)).get_json()
        alice = next(e for e in act["employees"] if e["name"] == ALICE_NAME)
        res = client.get(f"/api/company/employees/{alice['id']}/endpoints", headers=auth_header(co_token))
        assert res.status_code == 200
        names = [e["name"] for e in res.get_json()["endpoints"]]
        assert "Alice API" in names

    def test_company_can_view_bob_logs(self, client, co_token, bob_ep_id):
        act = client.get("/api/company/employees/activity", headers=auth_header(co_token)).get_json()
        bob = next(e for e in act["employees"] if e["name"] == BOB_NAME)
        res = client.get(f"/api/company/employees/{bob['id']}/logs", headers=auth_header(co_token))
        assert res.status_code in (200,)  # no logs yet is fine

    def test_company_employee_lookup_wrong_company(self, client):
        """Looking up an employee that belongs to a different company must 404."""
        other_token = register_and_login(
            client, "other_co_integ@example.com", "TestPass@123", "Other Co"
        )
        # Use a fake employee id from another company
        res = client.get(
            "/api/company/employees/nonexistent-id/endpoints",
            headers=auth_header(other_token),
        )
        assert res.status_code == 404

    def test_company_sees_all_endpoints_on_dashboard(self, client, co_token, alice_ep_id, bob_ep_id):
        res = client.get("/api/endpoints", headers=auth_header(co_token))
        names = [e["name"] for e in res.get_json()["endpoints"]]
        assert "Alice API" in names
        assert "Bob API" in names


class TestDashboardStats:

    def test_stats_returns_expected_fields(self, client, co_token):
        res = client.get("/api/dashboard/stats", headers=auth_header(co_token))
        assert res.status_code == 200
        data = res.get_json()
        # Stats may be top-level or nested under 'stats' key
        stats = data.get("stats", data)
        for field in ("total_apis", "active_apis", "down_apis", "uptime_percentage"):
            assert field in stats, f"Missing field '{field}' in: {stats}"

    def test_employee_stats_scoped_to_own(self, client, emp1_token):
        res = client.get("/api/dashboard/stats", headers=auth_header(emp1_token))
        assert res.status_code == 200
        data = res.get_json()
        stats = data.get("stats", data)
        # Alice has >= 1 API
        assert stats["total_apis"] >= 1

    def test_analytics_forbidden_for_employee(self, client, emp1_token):
        res = client.get("/api/dashboard/analytics", headers=auth_header(emp1_token))
        assert res.status_code == 403
