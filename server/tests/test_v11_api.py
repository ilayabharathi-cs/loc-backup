"""Tests for RetroVault V11 REST API Endpoints."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture
def auth_headers():
    res = client.post("/api/v1/auth/login", json={"username": "admin", "password": "AdminPass123!"})
    token = res.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_v11_api_workloads(auth_headers):
    # List workloads
    res = client.get("/api/v1/workloads/", headers=auth_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    # List providers
    prov_res = client.get("/api/v1/workloads/providers", headers=auth_headers)
    assert prov_res.status_code == 200
    types = [p["provider_type"] for p in prov_res.json()]
    assert "MSSQL" in types
    assert "POSTGRESQL" in types
    assert "WINDOWS_FILESYSTEM" in types
    assert "GENERIC_APP" in types

    # Create workload
    payload = {
        "client_id": "1",
        "type": "GENERIC_APP",
        "name": "Custom API Engine",
        "version": "2.4",
        "config": {"pre_hook": "echo pre", "timeout_seconds": 10}
    }
    create_res = client.post("/api/v1/workloads/", json=payload, headers=auth_headers)
    assert create_res.status_code == 201
    wl_data = create_res.json()
    assert wl_data["name"] == "Custom API Engine"


def test_v11_api_recovery_readiness(auth_headers):
    res = client.get("/api/v1/recovery-readiness/", headers=auth_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_v11_api_backup_chains(auth_headers):
    res = client.get("/api/v1/backup-chains/", headers=auth_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_v11_api_policy_orchestration(auth_headers):
    # Create draft policy version
    payload = {
        "policy_id": "pol-api-test",
        "definition": {"retention_days": 14, "rpo_hours": 4}
    }
    res = client.post("/api/v1/policy-orchestration/", json=payload, headers=auth_headers)
    assert res.status_code == 201
    data = res.json()
    assert data["lifecycle_state"] == "DRAFT"

    # Approve
    app_res = client.post(f"/api/v1/policy-orchestration/{data['id']}/approve", json={"notes": "API test approval"}, headers=auth_headers)
    assert app_res.status_code == 200
    assert app_res.json()["lifecycle_state"] == "APPROVED"


def test_v11_api_remediations(auth_headers):
    # Propose safe remediation
    payload = {
        "action_type": "TRIGGER_REPLICATION",
        "target_resource_type": "workload",
        "target_resource_id": "wl-api-1",
        "requires_dual_approval": False
    }
    res = client.post("/api/v1/remediations/", json=payload, headers=auth_headers)
    assert res.status_code == 201
    rem = res.json()
    assert rem["status"] == "PENDING_APPROVAL"

    # Propose prohibited destructive action -> 403 Forbidden
    bad_payload = {
        "action_type": "DELETE_RECOVERY_POINT",
        "target_resource_type": "recovery_point",
        "target_resource_id": "1",
        "requires_dual_approval": False
    }
    bad_res = client.post("/api/v1/remediations/", json=bad_payload, headers=auth_headers)
    assert bad_res.status_code == 403


def test_v11_api_dependencies(auth_headers):
    res = client.get("/api/v1/dependencies/", headers=auth_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    check_res = client.post(
        "/api/v1/dependencies/check-safe-delete",
        json={"resource_type": "CAS_OBJECT", "resource_id": "cas-nonexistent"},
        headers=auth_headers
    )
    assert check_res.status_code == 200
    assert "is_safe_to_delete" in check_res.json()
