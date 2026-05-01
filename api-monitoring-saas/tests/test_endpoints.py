"""
Test Suite 2: Endpoint CRUD, role-based visibility, and access isolation.
Covers: create, list, get, update, delete, toggle — for company and employee.
Key rule: employees see ONLY their own endpoints.
"""
import pytest
from tests.conftest import register_and_login, register_employee, auth_header, start_mock_server, mock_url

COMPANY_EMAIL = "test_company_ep@example.com"
COMPANY_PASS  = "TestPass@123"


@pytest.fixture(scope="module", autouse=True)
def _mock(request):
    start_mock_server()


@pytest.fixture(scope="module")
def company_token(client):
    return register_and_login(client, COMPANY_EMAIL, COMPANY_PASS, "Endpoint Test Co")


@pytest.fixture(scope="module")
def emp_token(client, company_token):
    return register_employee(client, company_token, "Emp Endpoint", "emp_endpoint@example.com")


def _create_endpoint(client, token, name="My API", path="/ok"):
    res = client.post(
        "/api/endpoints",
        json={"name": name, "url": mock_url(path), "method": "GET", "interval": 60},
        headers=auth_header(token),
    )
    return res


class TestEndpointCRUD:

    def test_create_endpoint_company(self, client, company_token):
        res = _create_endpoint(client, company_token, "Company API")
        assert res.status_code == 201
        data = res.get_json()
        assert data["endpoint"]["name"] == "Company API"

    def test_create_endpoint_employee(self, client, emp_token):
        res = _create_endpoint(client, emp_token, "Employee API")
        assert res.status_code == 201

    def test_create_endpoint_requires_name(self, client, company_token):
        """A name is required — backend validates this."""
        res = client.post(
            "/api/endpoints",
            json={"url": mock_url("/ok"), "method": "GET", "interval": 60},
            headers=auth_header(company_token),
        )
        assert res.status_code == 400

    def test_company_sees_all_endpoints(self, client, company_token):
        res = client.get("/api/endpoints", headers=auth_header(company_token))
        data = res.get_json()
        assert res.status_code == 200
        names = [e["name"] for e in data["endpoints"]]
        assert "Company API" in names

    def test_employee_sees_only_own_endpoints(self, client, emp_token, company_token):
        """Employee must NOT see company admin's endpoint."""
        emp_res = client.get("/api/endpoints", headers=auth_header(emp_token))
        emp_eps = [e["name"] for e in emp_res.get_json()["endpoints"]]
        assert "Company API" not in emp_eps
        assert "Employee API" in emp_eps

    def test_get_endpoint_by_id_own(self, client, company_token):
        res = _create_endpoint(client, company_token, "FetchMe")
        ep_id = res.get_json()["endpoint"]["id"]
        fetch = client.get(f"/api/endpoints/{ep_id}", headers=auth_header(company_token))
        assert fetch.status_code == 200
        data = fetch.get_json()
        # Response may be flat {name:...} or nested {endpoint:{name:...}}
        ep_name = data.get("name") or data.get("endpoint", {}).get("name")
        assert ep_name == "FetchMe"

    def test_employee_cannot_get_company_endpoint(self, client, company_token, emp_token):
        res = _create_endpoint(client, company_token, "CompanyOnly")
        ep_id = res.get_json()["endpoint"]["id"]
        fetch = client.get(f"/api/endpoints/{ep_id}", headers=auth_header(emp_token))
        assert fetch.status_code == 404  # not found for employee

    def test_update_endpoint(self, client, company_token):
        res = _create_endpoint(client, company_token, "UpdateMe")
        ep_id = res.get_json()["endpoint"]["id"]
        upd = client.put(
            f"/api/endpoints/{ep_id}",
            json={"name": "Updated Name"},
            headers=auth_header(company_token),
        )
        assert upd.status_code == 200
        assert upd.get_json()["endpoint"]["name"] == "Updated Name"

    def test_employee_cannot_update_company_endpoint(self, client, company_token, emp_token):
        res = _create_endpoint(client, company_token, "DontTouchMe")
        ep_id = res.get_json()["endpoint"]["id"]
        upd = client.put(
            f"/api/endpoints/{ep_id}",
            json={"name": "Hacked"},
            headers=auth_header(emp_token),
        )
        assert upd.status_code == 404

    def test_toggle_endpoint(self, client, company_token):
        res = _create_endpoint(client, company_token, "ToggleMe")
        ep_id = res.get_json()["endpoint"]["id"]
        toggle = client.patch(f"/api/endpoints/{ep_id}/toggle", headers=auth_header(company_token))
        assert toggle.status_code == 200
        assert toggle.get_json()["endpoint"]["is_active"] is False

    def test_delete_endpoint(self, client, company_token):
        res = _create_endpoint(client, company_token, "DeleteMe")
        ep_id = res.get_json()["endpoint"]["id"]
        delete = client.delete(f"/api/endpoints/{ep_id}", headers=auth_header(company_token))
        assert delete.status_code == 200
        # Verify gone
        fetch = client.get(f"/api/endpoints/{ep_id}", headers=auth_header(company_token))
        assert fetch.status_code == 404

    def test_delete_nonexistent(self, client, company_token):
        res = client.delete("/api/endpoints/nonexistent-id-abc", headers=auth_header(company_token))
        assert res.status_code == 404

    def test_api_key_masked_in_response(self, client, company_token):
        res = client.post(
            "/api/endpoints",
            json={"name": "Keyed", "url": mock_url("/ok"), "method": "GET",
                  "interval": 60, "api_key": "sk-supersecretkey123456"},
            headers=auth_header(company_token),
        )
        ep = res.get_json()["endpoint"]
        # Full key must never appear in response
        assert ep.get("api_key") is None or "supersecret" not in str(ep.get("api_key", ""))
