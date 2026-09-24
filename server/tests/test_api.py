import pytest
import sys
import os
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from app.database.connection import check_db_connection

client = TestClient(app)

@pytest.fixture(scope="module")
def admin_token():
    res = client.post("/api/v1/auth/login", json={"username": "admin", "password": "AdminPass123!"})
    assert res.status_code == 200
    data = res.json()["data"]
    return data["access_token"]

@pytest.fixture(scope="module")
def operator_token():
    res = client.post("/api/v1/auth/login", json={"username": "operator", "password": "Operator123!"})
    assert res.status_code == 200
    data = res.json()["data"]
    return data["access_token"]

@pytest.fixture(scope="module")
def viewer_token():
    res = client.post("/api/v1/auth/login", json={"username": "viewer", "password": "Viewer123!"})
    assert res.status_code == 200
    data = res.json()["data"]
    return data["access_token"]

# 1. Database Connection Test
def test_database_connection():
    assert check_db_connection() is True

# 2. Health Endpoint Test
def test_health_endpoint():
    res = client.get("/health")
    assert res.status_code == 200
    json_data = res.json()
    assert json_data["status"] == "ok"
    assert json_data["database"] == "connected"
    assert json_data["version"] == "1.0.0"

# 3. Login Tests
def test_login_success():
    res = client.post("/api/v1/auth/login", json={"username": "admin", "password": "AdminPass123!"})
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert "access_token" in body["data"]
    assert body["data"]["role"] == "admin"

def test_login_failure():
    res = client.post("/api/v1/auth/login", json={"username": "admin", "password": "WrongPassword"})
    assert res.status_code == 401
    body = res.json()
    assert body["success"] is False
    assert "error" in body

# 4. Unauthorized Request Test
def test_unauthorized_request():
    res = client.post("/api/v1/clients", json={"client_id": "TEST-UNAUTH"})
    assert res.status_code == 401

# 5. Client Listing Test
def test_list_clients():
    res = client.get("/api/v1/clients")
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert isinstance(body["data"], list)
    assert len(body["data"]) >= 20  # seeded 20 clients

# 6. Client Creation Test
def test_create_client(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    # Clean up test client if existing from previous run
    client.delete("/api/v1/clients/PC-TEST-99", headers=headers)

    payload = {
        "client_id": "PC-TEST-99",
        "device_id": "DEV-TEST-UUID-99",
        "hostname": "TEST-RIG-99",
        "os": "Windows 11 Pro",
        "os_version": "23H2",
        "ip_address": "192.168.1.199",
        "agent_version": "1.4.2",
        "status": "pending"
    }
    res = client.post("/api/v1/clients", json=payload, headers=headers)
    assert res.status_code == 201
    body = res.json()
    assert body["success"] is True
    assert body["data"]["client_id"] == "PC-TEST-99"

# 7. Client Approval Test
def test_approve_client(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    res = client.post("/api/v1/clients/PC-TEST-99/approve", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["data"]["status"] == "active"

# 8. Agent Heartbeat Test
def test_agent_heartbeat():
    payload = {
        "device_id": "DEV-TEST-UUID-99",
        "ip_address": "192.168.1.199",
        "agent_version": "1.4.2",
        "status": "active"
    }
    res = client.post("/api/v1/agents/heartbeat", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["data"]["status"] == "active"

# 9. Policy CRUD Test
def test_policy_crud(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    # Create
    create_payload = {
        "name": "QA Lab Policy",
        "description": "Policy for test machines",
        "backup_type": "incremental",
        "change_detection": "usn_journal",
        "rpo_target_seconds": 120,
        "compression_enabled": True,
        "encryption_enabled": True,
        "cpu_limit_percent": 15,
        "network_limit_mbps": 100,
        "retention_days": 7,
        "paths": [
            {"path_type": "universal", "path_value": r"%USERPROFILE%\Documents", "is_excluded": False},
            {"path_type": "universal", "path_value": r"%TEMP%", "is_excluded": True}
        ]
    }
    res = client.post("/api/v1/policies", json=create_payload, headers=headers)
    assert res.status_code == 201
    created_id = res.json()["data"]["id"]

    # Read
    res_get = client.get(f"/api/v1/policies/{created_id}")
    assert res_get.status_code == 200
    assert res_get.json()["data"]["name"] == "QA Lab Policy"

    # Update
    res_patch = client.patch(f"/api/v1/policies/{created_id}", json={"description": "Updated QA policy"}, headers=headers)
    assert res_patch.status_code == 200
    assert res_patch.json()["data"]["description"] == "Updated QA policy"

    # Delete
    res_del = client.delete(f"/api/v1/policies/{created_id}", headers=headers)
    assert res_del.status_code == 200

# 10. Job Creation & Cancellation Test
def test_job_create_and_cancel(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    res_create = client.post("/api/v1/jobs", json={"client_id": "PC-001"}, headers=headers)
    assert res_create.status_code == 201
    job = res_create.json()["data"]
    assert job["status"] == "running"

    res_cancel = client.post(f"/api/v1/jobs/{job['job_id']}/cancel", headers=headers)
    assert res_cancel.status_code == 200
    assert res_cancel.json()["data"]["status"] == "cancelled"

# 11. Dashboard Summary Test
def test_dashboard_summary():
    res = client.get("/api/v1/dashboard/summary")
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    data = body["data"]
    assert "total_clients" in data
    assert "online_clients" in data
    assert "successful_backups" in data
    assert "storage_total" in data
    assert len(data["recent_jobs"]) > 0

# 12. Restore Job Creation & Cross-Client Safeguard Test
def test_restore_job_safeguard(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Recovery point from seed
    rp_res = client.get("/api/v1/backups/recovery-points")
    assert rp_res.status_code == 200
    rps = rp_res.json()["data"]
    target_rp = next((r for r in rps if r.get("client_id") == 1), rps[0])
    rp_id = target_rp["id"]

    # Same client restore (Allowed without explicit acknowledgement)
    same_client_payload = {
        "source_client_id": "PC-001",
        "target_client_id": "PC-001",
        "recovery_point_id": rp_id,
        "source_path": r"C:\Users\Arun\Documents\Report.docx",
        "target_path": r"C:\Users\Arun\Documents\Report.docx",
        "acknowledge_cross_client": False
    }
    res_same = client.post("/api/v1/restore/jobs", json=same_client_payload, headers=headers)
    assert res_same.status_code == 201

    # Cross-client restore WITHOUT acknowledgement (Must fail with 400)
    cross_client_unauth = {
        "source_client_id": "PC-001",
        "target_client_id": "PC-002",
        "recovery_point_id": rp_id,
        "source_path": r"C:\Users\Arun\Documents\Report.docx",
        "target_path": r"C:\Restored\Report.docx",
        "acknowledge_cross_client": False
    }
    res_cross_unauth = client.post("/api/v1/restore/jobs", json=cross_client_unauth, headers=headers)
    assert res_cross_unauth.status_code == 400

    # Cross-client restore WITH explicit acknowledgement (Must succeed)
    cross_client_auth = {
        "source_client_id": "PC-001",
        "target_client_id": "PC-002",
        "recovery_point_id": rp_id,
        "source_path": r"C:\Users\Arun\Documents\Report.docx",
        "target_path": r"C:\Restored\Report.docx",
        "acknowledge_cross_client": True
    }
    res_cross_auth = client.post("/api/v1/restore/jobs", json=cross_client_auth, headers=headers)
    assert res_cross_auth.status_code == 201
    assert res_cross_auth.json()["data"]["status"] == "completed"

# 13. RBAC Enforcement Test
def test_rbac_enforcement(admin_token, operator_token, viewer_token):
    # Viewer tries to create client -> Should fail 403 Forbidden
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}
    res_viewer = client.post(
        "/api/v1/clients",
        json={"client_id": "PC-VIEWER-TEST", "device_id": "DEV-V-1", "hostname": "H", "os": "Win", "ip_address": "1.1.1.1", "agent_version": "1"},
        headers=viewer_headers
    )
    assert res_viewer.status_code == 403

    # Operator tries to delete client (admin only) -> Should fail 403 Forbidden
    op_headers = {"Authorization": f"Bearer {operator_token}"}
    res_op = client.delete("/api/v1/clients/PC-TEST-99", headers=op_headers)
    assert res_op.status_code == 403

    # Clean up test client with admin token
    client.delete("/api/v1/clients/PC-TEST-99", headers={"Authorization": f"Bearer {admin_token}"})

