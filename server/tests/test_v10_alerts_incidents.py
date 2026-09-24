"""Tests for RetroVault V10 Operational Alert Engine & Incident Correlation."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database.session import SessionLocal
from app.services.observability.alert_evaluator import AlertEvaluator
from app.services.observability.incident_service import IncidentService

client = TestClient(app)


@pytest.fixture
def auth_headers():
    res = client.post("/api/v1/auth/login", json={"username": "admin", "password": "AdminPass123!"})
    token = res.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_alert_evaluation_deduplication_and_resolution():
    db = SessionLocal()
    try:
        evaluator = AlertEvaluator(db)

        # 1. Trigger initial alert
        a1 = evaluator.trigger_alert(
            alert_type="REPOSITORY_LOW_SPACE",
            resource_id="repo-primary",
            source="storage",
            title="Repository Low Disk Space",
            message="Free capacity below 10%",
            severity="WARNING",
            threshold_value=10.0,
            observed_value=7.5
        )
        assert a1.alert_id is not None
        assert a1.occurrence_count == 1
        assert a1.status == "ACTIVE"

        # 2. Trigger identical alert -> deduplication occurs
        a2 = evaluator.trigger_alert(
            alert_type="REPOSITORY_LOW_SPACE",
            resource_id="repo-primary",
            source="storage",
            title="Repository Low Disk Space",
            message="Free capacity below 10%",
            severity="WARNING",
            threshold_value=10.0,
            observed_value=6.8
        )
        assert a2.alert_id == a1.alert_id
        assert a2.occurrence_count == 2

        # 3. Acknowledge alert
        acked = evaluator.acknowledge_alert(a1.alert_id, "operator-1")
        assert acked is not None
        assert acked.status == "ACKNOWLEDGED"

        # 4. Resolve alert
        resolved = evaluator.resolve_alert(a1.alert_id, "operator-1")
        assert resolved is not None
        assert resolved.status == "RESOLVED"
    finally:
        db.close()


def test_alert_storm_correlation_into_incident():
    db = SessionLocal()
    try:
        evaluator = AlertEvaluator(db)
        incident_service = IncidentService(db)

        # Create multiple alerts triggered by a single repository outage
        alt1 = evaluator.trigger_alert("BACKUP_MISSED", "client-srv-1", "backup", "Backup Failed", "Target repo unreachable", "HIGH")
        alt2 = evaluator.trigger_alert("BACKUP_MISSED", "client-srv-2", "backup", "Backup Failed", "Target repo unreachable", "HIGH")
        alt3 = evaluator.trigger_alert("REPLICATION_LAG", "repo-nas-01", "replication", "Replication Blocked", "Source offline", "HIGH")

        # Correlate alerts into a single incident to prevent alert storm
        inc = incident_service.correlate_alerts(
            root_event="Repository NAS-01 Hardware Outage",
            title="Widespread Backup Failure from Repository Outage",
            alert_ids=[alt1.alert_id, alt2.alert_id, alt3.alert_id],
            affected_resources=["client-srv-1", "client-srv-2", "repo-nas-01"],
            severity="HIGH",
            relationship_type="CAUSAL"
        )
        assert inc.incident_id.startswith("INC-")
        assert inc.status == "DETECTED"

        # Progress lifecycle: INVESTIGATING -> MITIGATING -> RESOLVED
        inc_inv = incident_service.update_incident_status(inc.incident_id, "INVESTIGATING", "sysadmin", "Replacing disk controller")
        assert inc_inv.status == "INVESTIGATING"

        inc_res = incident_service.update_incident_status(inc.incident_id, "RESOLVED", "sysadmin", "Controller replaced, repository online")
        assert inc_res.status == "RESOLVED"
        assert inc_res.resolved_at is not None
    finally:
        db.close()


def test_alerts_and_incidents_rest_api(auth_headers):
    # 1. Trigger alert via API
    res = client.post("/api/v1/operations/alerts", json={
        "alert_type": "SCHEDULER_BACKLOG",
        "resource_id": "queue-global",
        "source": "scheduler",
        "title": "Scheduler Backlog Growing",
        "message": "More than 50 jobs pending execution",
        "severity": "WARNING",
        "threshold_value": 50.0,
        "observed_value": 65.0
    }, headers=auth_headers)
    assert res.status_code == 200
    alert_id = res.json()["alert_id"]

    # 2. List alerts
    list_res = client.get("/api/v1/operations/alerts", headers=auth_headers)
    assert list_res.status_code == 200
    assert any(a["alert_id"] == alert_id for a in list_res.json())

    # 3. Correlate into incident
    inc_res = client.post("/api/v1/operations/incidents", json={
        "root_event": "Cluster Node Network Partition",
        "title": "API Scheduler Partition Incident",
        "alert_ids": [alert_id],
        "affected_resources": ["queue-global"],
        "severity": "MEDIUM",
        "relationship_type": "CAUSAL"
    }, headers=auth_headers)
    assert inc_res.status_code == 200
    inc_id = inc_res.json()["incident_id"]

    # 4. Update incident status
    upd_res = client.put(f"/api/v1/operations/incidents/{inc_id}", json={
        "status": "MITIGATING",
        "note": "Re-routing cluster traffic"
    }, headers=auth_headers)
    assert upd_res.status_code == 200
    assert upd_res.json()["status"] == "MITIGATING"
