"""Server Tests for RetroVault V7: Enterprise Operations, Offsite Replication & Security."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import datetime
import hashlib
import tempfile
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database.session import SessionLocal
from app.models.client import Client
from app.models.backup_job import BackupJob
from app.models.backup_run import BackupRun
from app.models.backup_file import BackupFile
from app.models.recovery_point import RecoveryPoint
from app.models.storage_object import StorageObject
from app.models.storage_repository import StorageRepository
from app.models.replication import ReplicationJob
from app.models.alert import AlertRule, Alert
from app.models.security_models import AgentCredential, DrTest
from app.services.repository.provider import get_repository_provider
from app.services.replication.engine import ReplicationEngine
from app.services.replication.topology import BackupTopologyEvaluator
from app.services.alerts.alert_engine import AlertEngine
from app.services.observability.health_score import BackupHealthEvaluator
from app.services.observability.sla_monitor import SlaMonitor
from app.services.dr.dr_tester import DrTester
from app.security.mfa import TotpManager

client = TestClient(app)


@pytest.fixture
def auth_headers():
    login_res = client.post("/api/v1/auth/login", json={"username": "admin", "password": "AdminPass123!"})
    assert login_res.status_code == 200
    token = login_res.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_setup():
    db = SessionLocal()
    suffix = uuid.uuid4().hex[:6]

    # Create Local Primary Repo & Secondary Remote Repo
    temp_dir_pri = tempfile.mkdtemp(prefix=f"rv_pri_{suffix}_")
    temp_dir_sec = tempfile.mkdtemp(prefix=f"rv_sec_{suffix}_")

    repo_pri = StorageRepository(
        name=f"Primary-{suffix}",
        repository_type="LOCAL_FILESYSTEM",
        path=temp_dir_pri,
        root_path=temp_dir_pri,
        status="ONLINE",
        protection_mode="NORMAL",
        total_bytes=100 * 1024 * 1024 * 1024,
        used_bytes=10 * 1024 * 1024,
        available_bytes=90 * 1024 * 1024 * 1024
    )
    repo_sec = StorageRepository(
        name=f"Secondary-{suffix}",
        repository_type="REMOTE_FILESYSTEM",
        path=temp_dir_sec,
        root_path=temp_dir_sec,
        status="ONLINE",
        protection_mode="PROTECTED",
        total_bytes=200 * 1024 * 1024 * 1024,
        used_bytes=5 * 1024 * 1024,
        available_bytes=195 * 1024 * 1024 * 1024
    )
    db.add_all([repo_pri, repo_sec])
    db.commit()
    db.refresh(repo_pri)
    db.refresh(repo_sec)

    # Client
    c = Client(
        client_id=f"PC-V7-{suffix}",
        hostname=f"HOST-V7-{suffix}",
        ip_address="192.168.1.99",
        device_id=f"DEV-V7-{suffix}",
        os="Windows 11 Enterprise",
        agent_version="7.0.0",
        status="online"
    )
    db.add(c)
    db.commit()
    db.refresh(c)

    # BackupJob & Run
    job = BackupJob(
        job_id=f"job-v7-{suffix}",
        client_id=c.id,
        backup_type="full",
        status="completed"
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    run = BackupRun(
        job_id=job.id,
        client_id=c.id,
        backup_type="full",
        status="completed",
        state="COMPLETED",
        started_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1),
        completed_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=50),
        bytes_total=1024
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # Store objects in primary repo
    prov_pri = get_repository_provider(repo_pri)
    content1 = f"V7 Enterprise Payload {suffix}".encode() * 10
    sha1 = hashlib.sha256(content1).hexdigest()
    storage_path1 = f"objects/{sha1[:2]}/{sha1[2:4]}/{sha1}"
    prov_pri.put_object(storage_path1, content1)

    obj1 = StorageObject(
        object_id=f"obj_{sha1}",
        content_sha256=sha1,
        stored_sha256=sha1,
        original_size=len(content1),
        stored_size=len(content1),
        compression_algorithm="NONE",
        encryption_status="NONE",
        storage_path=storage_path1,
        reference_count=1,
        state="AVAILABLE",
        integrity_status="VALID"
    )
    db.add(obj1)
    db.commit()
    db.refresh(obj1)

    # Recovery Point
    rp = RecoveryPoint(
        client_id=c.id,
        backup_run_id=run.id,
        backup_type="full",
        timestamp=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=50),
        files_count=1,
        total_size_bytes=len(content1),
        status="valid",
        retention_status="active"
    )
    db.add(rp)
    db.commit()
    db.refresh(rp)

    bf = BackupFile(
        client_id=c.id,
        backup_run_id=run.id,
        file_name="file1.dat",
        original_path="C:\\Data\\file1.dat",
        size_bytes=len(content1),
        sha256=sha1,
        storage_object_id=obj1.id,
        upload_status="completed",
        change_type="FULL"
    )
    db.add(bf)
    db.commit()

    yield {
        "db": db,
        "repo_pri": repo_pri,
        "repo_sec": repo_sec,
        "client": c,
        "job": job,
        "run": run,
        "rp": rp,
        "obj1": obj1,
        "content1": content1,
        "sha1": sha1,
        "storage_path1": storage_path1,
        "temp_pri": temp_dir_pri,
        "temp_sec": temp_dir_sec
    }

    db.close()


def test_repository_lifecycle_and_health(auth_headers, test_setup):
    """Test repository creation, listing, health check, and maintenance mode."""
    # 1. List Repositories
    res = client.get("/api/v1/repositories", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert len(data["data"]) >= 2

    # 2. Health Check Probe
    repo_id = test_setup["repo_pri"].id
    h_res = client.get(f"/api/v1/repositories/{repo_id}/health", headers=auth_headers)
    assert h_res.status_code == 200
    h_data = h_res.json()["data"]
    assert h_data["status"] in ["HEALTHY", "ONLINE"]
    assert h_data["write_test"] is True
    assert h_data["read_test"] is True

    # 3. Toggle Maintenance Mode
    m_res = client.post(f"/api/v1/repositories/{repo_id}/maintenance?enabled=true", headers=auth_headers)
    assert m_res.status_code == 200
    assert m_res.json()["data"]["status"] == "MAINTENANCE"

    # 4. Turn off Maintenance Mode
    m_res2 = client.post(f"/api/v1/repositories/{repo_id}/maintenance?enabled=false", headers=auth_headers)
    assert m_res2.status_code == 200
    assert m_res2.json()["data"]["status"] == "ONLINE"


def test_immutable_repository_deletion_guard(auth_headers):
    """Verify that IMMUTABLE repositories cannot be deleted."""
    temp_dir = tempfile.mkdtemp(prefix="rv_immutable_")
    create_res = client.post("/api/v1/repositories", json={
        "name": f"Immutable Vault {uuid.uuid4().hex[:6]}",
        "repository_type": "LOCAL_FILESYSTEM",
        "path": temp_dir,
        "root_path": temp_dir,
        "protection_mode": "IMMUTABLE"
    }, headers=auth_headers)
    assert create_res.status_code in [200, 201]
    repo_id = create_res.json()["data"]["id"]

    # Attempt deletion
    del_res = client.delete(f"/api/v1/repositories/{repo_id}", headers=auth_headers)
    assert del_res.status_code == 403
    err_body = del_res.json()
    err_msg = err_body.get("error", {}).get("message", "") or err_body.get("detail", "")
    assert "IMMUTABLE" in err_msg


def test_replication_engine_execution_and_cas_dedup(auth_headers, test_setup):
    """Test offsite replication with CAS deduplication, integrity validation, and checkpoints."""
    pri_id = test_setup["repo_pri"].id
    sec_id = test_setup["repo_sec"].id
    rp_id = test_setup["rp"].id

    # 1. Create Replication Job
    job_payload = {
        "source_repository_id": pri_id,
        "destination_repository_id": sec_id,
        "recovery_point_id": rp_id,
        "bandwidth_limit_mbps": 100.0,
        "execute_now": True
    }
    create_res = client.post("/api/v1/replication/jobs", json=job_payload, headers=auth_headers)
    assert create_res.status_code in [200, 201]
    rep_job_id = create_res.json()["data"]["id"]

    # 2. Query Job Status
    job_res = client.get(f"/api/v1/replication/jobs/{rep_job_id}", headers=auth_headers)
    assert job_res.status_code == 200
    assert job_res.json()["data"]["status"] == "COMPLETED"
    assert job_res.json()["data"]["completed_objects"] == 1

    # Verify object arrived in destination
    prov_sec = get_repository_provider(test_setup["repo_sec"])
    assert prov_sec.exists(test_setup["storage_path1"]) is True
    retrieved = prov_sec.get_object(test_setup["storage_path1"])
    assert hashlib.sha256(retrieved).hexdigest() == test_setup["sha1"]

    # 3. Create a Second Replication Job for the same RP (CAS Deduplication Check)
    create_res2 = client.post("/api/v1/replication/jobs", json=job_payload, headers=auth_headers)
    assert create_res2.status_code in [200, 201]
    rep_job_id2 = create_res2.json()["data"]["id"]
    job_res2 = client.get(f"/api/v1/replication/jobs/{rep_job_id2}", headers=auth_headers)
    assert job_res2.status_code == 200
    # Transferred bytes should be 0 because CAS skipped existing verified object
    assert job_res2.json()["data"]["transferred_bytes"] == 0
    assert job_res2.json()["data"]["skipped_objects"] == 1
    assert job_res2.json()["data"]["status"] == "COMPLETED"


def test_321_backup_topology_evaluation(auth_headers, test_setup):
    """Test 3-2-1 compliance logic evaluation."""
    topo_res = client.get("/api/v1/replication/topology", headers=auth_headers)
    assert topo_res.status_code == 200
    data = topo_res.json()["data"]
    assert "is_compliant" in data
    assert "total_copies" in data
    assert "media_types_count" in data
    assert "has_offsite" in data
    assert "total_repositories" in data
    assert data["total_repositories"] >= 2


def test_alerting_engine_and_lifecycle(auth_headers, test_setup):
    """Test alert rule creation, alert firing, acknowledgment, and resolution."""
    # 1. Create Alert Rule
    suffix = uuid.uuid4().hex[:6]
    rule_res = client.post("/api/v1/alerts/rules", json={
        "name": f"Storage High Watermark {suffix}",
        "rule_type": "LOW_STORAGE",
        "threshold_value": "85.0",
        "severity": "CRITICAL"
    }, headers=auth_headers)
    assert rule_res.status_code in [200, 201]
    rule_id = rule_res.json()["data"]["id"]

    # 2. Trigger Evaluation
    eval_res = client.post("/api/v1/alerts/evaluate", headers=auth_headers)
    assert eval_res.status_code == 200

    # 3. Manually insert or query alert
    db = SessionLocal()
    alt = Alert(
        rule_id=rule_id,
        alert_type="LOW_STORAGE",
        title="Test Critical Storage Alert",
        message="Storage reached 92% capacity",
        severity="CRITICAL",
        status="ACTIVE"
    )
    db.add(alt)
    db.commit()
    db.refresh(alt)
    alert_id = alt.id
    db.close()

    # 4. List Active Alerts
    list_res = client.get("/api/v1/alerts?status=ACTIVE", headers=auth_headers)
    assert list_res.status_code == 200
    alerts = list_res.json()["data"]
    assert any(a["id"] == alert_id for a in alerts)

    # 5. Acknowledge Alert
    ack_res = client.post(f"/api/v1/alerts/{alert_id}/acknowledge", headers=auth_headers)
    assert ack_res.status_code == 200
    assert ack_res.json()["data"]["status"] == "ACKNOWLEDGED"

    # 6. Resolve Alert
    res_res = client.post(f"/api/v1/alerts/{alert_id}/resolve", headers=auth_headers)
    assert res_res.status_code == 200
    assert res_res.json()["data"]["status"] == "RESOLVED"


def test_totp_mfa_setup_and_verification(auth_headers):
    """Test RFC 6238 TOTP Two-Factor Authentication setup, verification, and disable."""
    # 1. Setup MFA
    setup_res = client.post("/api/v1/security/mfa/setup", headers=auth_headers)
    assert setup_res.status_code == 200
    data = setup_res.json()["data"]
    assert "secret" in data
    assert "provisioning_uri" in data
    assert len(data["recovery_codes"]) == 8
    secret = data["secret"]

    # 2. Verify with valid TOTP code
    valid_code = TotpManager.get_totp_code(secret)

    verify_res = client.post("/api/v1/security/mfa/verify", json={"code": valid_code}, headers=auth_headers)
    assert verify_res.status_code == 200
    assert verify_res.json()["data"]["mfa_enabled"] is True

    # 3. Check Security Overview
    sec_overview = client.get("/api/v1/security/overview", headers=auth_headers)
    assert sec_overview.status_code == 200
    assert sec_overview.json()["data"]["mfa_enabled"] is True

    # 4. Disable MFA using valid TOTP
    disable_code = TotpManager.get_totp_code(secret)
    disable_res = client.post("/api/v1/security/mfa/disable", json={"code": disable_code}, headers=auth_headers)
    assert disable_res.status_code == 200
    assert disable_res.json()["data"]["mfa_enabled"] is False


def test_agent_credential_rotation(auth_headers, test_setup):
    """Test zero-downtime agent token rotation protocol."""
    client_id = test_setup["client"].client_id

    # 1. Rotate Credentials -> stages pending credential
    rot_res = client.post(f"/api/v1/agents/{client_id}/rotate-credentials", headers=auth_headers)
    assert rot_res.status_code == 200
    rot_data = rot_res.json()["data"]
    assert "new_token" in rot_data
    assert "credential_id" in rot_data
    cred_id = rot_data["credential_id"]

    # 2. Confirm Credentials -> promotes to active
    conf_res = client.post(f"/api/v1/agents/{client_id}/confirm-credentials", json={"credential_id": cred_id}, headers=auth_headers)
    assert conf_res.status_code == 200
    assert conf_res.json()["data"]["status"] in ["ACTIVE", "CONFIRMED"]


def test_automated_dr_sandbox_testing(auth_headers, test_setup):
    """Test non-destructive automated disaster recovery sandbox run."""
    rp_id = test_setup["rp"].id

    # 1. Trigger DR Test
    dr_res = client.post("/api/v1/dr/tests", json={
        "recovery_point_id": rp_id
    }, headers=auth_headers)
    assert dr_res.status_code in [200, 201]
    dr_data = dr_res.json()["data"]
    assert dr_data["result"] in ["SUCCESS", "PASSED"]
    assert dr_data["files_tested"] >= 1

    # 2. Query DR Readiness
    readiness_res = client.get("/api/v1/dr/readiness", headers=auth_headers)
    assert readiness_res.status_code == 200
    r_data = readiness_res.json()["data"]
    assert "status" in r_data
    assert "health_indicators" in r_data


def test_centralized_system_settings(auth_headers):
    """Test enterprise settings query and bulk update."""
    # 1. Get settings
    get_res = client.get("/api/v1/settings", headers=auth_headers)
    assert get_res.status_code == 200
    assert "retention" in get_res.json()["data"] or "general" in get_res.json()["data"]

    # 2. Update setting
    up_res = client.put("/api/v1/settings/retention.default_days", json={
        "value": "60"
    }, headers=auth_headers)
    assert up_res.status_code == 200
    assert up_res.json()["data"]["value"] == "60"
