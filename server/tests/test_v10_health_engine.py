"""Tests for RetroVault V10 System Health & 14 Component Health Check Engine."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database.session import SessionLocal
from app.services.observability.health_service import HealthCheckService

client = TestClient(app)


@pytest.fixture
def auth_headers():
    res = client.post("/api/v1/auth/login", json={"username": "admin", "password": "AdminPass123!"})
    token = res.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_health_service_evaluation():
    db = SessionLocal()
    try:
        service = HealthCheckService(db)
        result = service.evaluate_all(check_type="deep_health")

        assert "overall_status" in result
        assert result["overall_status"] in ["HEALTHY", "WARNING", "DEGRADED", "CRITICAL"]
        assert "overall_reason" in result
        assert len(result["overall_reason"]) > 0
        assert "components" in result

        comps = result["components"]
        # Verify all 14 mandatory components are checked
        expected = [
            "api", "database", "cluster", "leader", "workers", "scheduler",
            "repositories", "storage", "replication", "agents", "backup_freshness",
            "restore_readiness", "security_engine", "alerting"
        ]
        for c in expected:
            assert c in comps
            assert "status" in comps[c]
            assert "latency_ms" in comps[c]
            assert "reason" in comps[c]
    finally:
        db.close()


def test_health_rest_api(auth_headers):
    res = client.get("/api/v1/operations/health?check_type=deep_health", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "overall_status" in data
    assert "overall_reason" in data
    assert "components" in data
    assert len(data["components"]) == 14
