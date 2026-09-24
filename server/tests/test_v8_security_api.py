"""Server Tests for RetroVault V8: Ransomware Resilience, Advanced Security & Enterprise Scale."""

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
from app.models.backup_policy import BackupPolicy
from app.models.backup_run import BackupRun
from app.models.recovery_point import RecoveryPoint
from app.models.storage_object import StorageObject
from app.models.storage_repository import StorageRepository
from app.models.security_v8_models import (
    SecurityEvent, SecurityIncident, SecurityProfile, ClientGroup,
    PolicyVersion, ConfigurationDrift, IntegrityScan, DeletionGuard, SecuritySimulation
)
from app.services.security.entropy_analyzer import EntropyAnalyzer
from app.services.security.anomaly_detector import AnomalyDetector
from app.services.security.integrity_monitor import IntegrityMonitor
from app.services.security.deletion_guard import DeletionGuardService
from app.services.repository.immutable_provider import ImmutabilityProvider
from app.services.fleet.policy_orchestrator import PolicyOrchestrator
from app.services.fleet.drift_detector import DriftDetector
from app.services.security.clean_recovery_selector import CleanRecoverySelector
from app.services.security.simulation_engine import SimulationEngine
from app.services.scheduler.high_scale_scheduler import HighScaleScheduler

client = TestClient(app)


@pytest.fixture
def auth_headers():
    login_res = client.post("/api/v1/auth/login", json={"username": "admin", "password": "AdminPass123!"})
    assert login_res.status_code == 200
    token = login_res.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_entropy_analyzer_and_baselines():
    # 1. Plain text entropy should be low (< 5.0)
    plain_text = b"This is a standard English text file with repetitive words and low randomness. " * 30
    plain_ent = EntropyAnalyzer.calculate_shannon_entropy(plain_text)
    assert plain_ent < 5.0

    eval_plain = EntropyAnalyzer.evaluate_file_entropy("notes.txt", plain_ent)
    assert eval_plain["is_suspicious"] is False

    # 2. Random bytes should have high entropy (> 7.5)
    random_bytes = os.urandom(4096)
    rand_ent = EntropyAnalyzer.calculate_shannon_entropy(random_bytes)
    assert rand_ent > 7.5

    # High entropy on a text or unknown file should be flagged
    eval_rand = EntropyAnalyzer.evaluate_file_entropy("notes.txt", rand_ent)
    assert eval_rand["is_suspicious"] is True
    assert any("High entropy" in r for r in eval_rand["reasons"])

    # 3. Known ransomware extension should be flagged
    eval_ext = EntropyAnalyzer.evaluate_file_entropy("invoice.pdf.locked", 4.0)
    assert eval_ext["is_suspicious"] is True
    assert any("ransomware extension" in r for r in eval_ext["reasons"])

    # 4. 3-Block sampling on large payload
    large_payload = plain_text * 5000
    sample_res = EntropyAnalyzer.sample_and_calculate_entropy(large_payload, sample_block_size=1024)
    assert sample_res["sampled_bytes"] > 0
    assert sample_res["overall_entropy"] < 5.0


def test_anomaly_detection_multi_signal_and_security_hold():
    db = SessionLocal()
    suffix = uuid.uuid4().hex[:6]

    # Create client, run, and recovery point
    c = Client(
        client_id=f"cli-{suffix}",
        hostname=f"host-{suffix}",
        device_id=f"dev-{suffix}",
        os="Windows",
        ip_address="192.168.1.50",
        agent_version="8.0.0",
        status="active"
    )
    db.add(c)
    db.commit()

    job = BackupJob(job_id=f"job-{suffix}", client_id=c.id, backup_type="incremental", status="completed")
    db.add(job)
    db.commit()

    run = BackupRun(
        job_id=job.id,
        client_id=c.id,
        backup_type="incremental",
        status="completed",
        files_modified=50,
        files_deleted=20,
        bytes_processed=1000000,
        bytes_uploaded=995000,  # near 1.0 compression ratio -> collapse
    )
    db.add(run)
    db.commit()

    rp = RecoveryPoint(
        client_id=c.id,
        backup_run_id=run.id,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
        status="valid",
        retention_status="active",
        protection_state="NORMAL"
    )
    db.add(rp)
    db.commit()

    # Pass simulated metadata with suspicious ransomware extension and high entropy
    files_meta = [
        {"path": "c:/data/database.mdf.locked", "entropy": 7.95, "action": "MODIFIED"},
        {"path": "c:/data/documents.xlsx.locked", "entropy": 7.98, "action": "MODIFIED"}
    ]

    detector = AnomalyDetector(db)
    result = detector.evaluate_backup_run(run.id, files_metadata=files_meta)

    assert result["anomalous"] is True
    assert result["score"] >= 60
    assert result["security_hold_applied"] is True

    # Verify recovery point was placed on SECURITY_HOLD
    db.refresh(rp)
    assert rp.protection_state == "SECURITY_HOLD"
    assert rp.security_hold_until is not None

    db.close()


def test_continuous_integrity_monitor_and_quarantine():
    db = SessionLocal()
    suffix = uuid.uuid4().hex[:6]
    temp_dir = tempfile.mkdtemp(prefix=f"rv_integrity_{suffix}_")

    repo = StorageRepository(
        name=f"IntegrityRepo-{suffix}",
        repository_type="LOCAL_FILESYSTEM",
        path=temp_dir,
        root_path=temp_dir,
        status="ONLINE",
        total_bytes=10000000
    )
    db.add(repo)
    db.commit()

    # Create real file in repository objects layout
    os.makedirs(os.path.join(temp_dir, "objects", "ab", "cd"), exist_ok=True)
    obj_path = os.path.join(temp_dir, "objects", "ab", "cd", f"obj_{suffix}.dat")
    content = b"Authentic uncorrupted content block"
    with open(obj_path, "wb") as f:
        f.write(content)

    real_sha = hashlib.sha256(content).hexdigest()
    rel_path = os.path.relpath(obj_path, temp_dir).replace("\\", "/")

    # Add valid StorageObject
    so_valid = StorageObject(
        object_id=f"obj_val_{suffix}",
        content_sha256=real_sha,
        stored_sha256=real_sha,
        original_size=len(content),
        stored_size=len(content),
        storage_path=rel_path,
        state="AVAILABLE"
    )

    # Add corrupted StorageObject (expected hash won't match disk content)
    obj_corrupt_path = os.path.join(temp_dir, "objects", "ab", "cd", f"obj_bad_{suffix}.dat")
    with open(obj_corrupt_path, "wb") as f:
        f.write(b"Tampered bits inside storage object")
    rel_bad_path = os.path.relpath(obj_corrupt_path, temp_dir).replace("\\", "/")

    so_bad = StorageObject(
        object_id=f"obj_bad_{suffix}",
        content_sha256="0000000000000000000000000000000000000000000000000000000000000000",
        stored_sha256="0000000000000000000000000000000000000000000000000000000000000000",
        original_size=30,
        stored_size=30,
        storage_path=rel_bad_path,
        state="AVAILABLE"
    )

    db.add(so_valid)
    db.add(so_bad)
    db.commit()

    monitor = IntegrityMonitor(db, repository_id=repo.id)
    scan_res = monitor.run_integrity_scan(repository_id=repo.id, scan_type="FULL")

    assert scan_res["total_objects"] >= 2
    assert scan_res["corrupted_objects"] >= 1
    assert scan_res["valid_objects"] >= 1

    db.refresh(so_bad)
    assert so_bad.state == "CORRUPTED"
    assert so_bad.quarantined_at is not None

    db.close()


def test_mass_deletion_guard_and_dual_auth():
    db = SessionLocal()
    suffix = uuid.uuid4().hex[:6]

    # Create dummy recovery points with valid run and timestamp
    job_dummy = BackupJob(job_id=f"job-dummy-{suffix}", client_id=1, backup_type="full", status="completed")
    db.add(job_dummy)
    db.commit()

    run_dummy = BackupRun(job_id=job_dummy.id, client_id=1, backup_type="full", status="completed")
    db.add(run_dummy)
    db.commit()

    rp_ids = []
    for i in range(10):
        rp = RecoveryPoint(
            client_id=1,
            backup_run_id=run_dummy.id,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
            status="valid",
            retention_status="active",
            protection_state="NORMAL"
        )
        db.add(rp)
        db.commit()
        rp_ids.append(rp.id)

    guard_svc = DeletionGuardService(db)

    # 1. High volume deletion request (10 recovery points > default 5)
    eval_res = guard_svc.evaluate_request(
        request_type="DELETE_RECOVERY_POINTS",
        target_resource_type="RECOVERY_POINTS",
        target_resource_id="multiple",
        payload={"recovery_point_ids": rp_ids},
        requester_username="alice",
        requester_id=10
    )
    assert eval_res["requires_approval"] is True
    assert eval_res["risk_score"] >= 40
    guard_id = eval_res["guard_id"]

    # 2. Requester attempting self-approval on high-risk request should be rejected (dual authorization)
    self_appr = guard_svc.approve_request(guard_id, approver_username="alice", mfa_verified=True)
    assert self_appr.get("success") is False

    # 3. Independent administrator approving with MFA should succeed
    admin_appr = guard_svc.approve_request(guard_id, approver_username="bob_admin", mfa_verified=True)
    assert admin_appr.get("status") == "APPROVED"

    db.close()


def test_immutable_provider_capabilities():
    db = SessionLocal()
    suffix = uuid.uuid4().hex[:6]

    repo = StorageRepository(
        name=f"ImmutableRepo-{suffix}",
        repository_type="LOCAL_FILESYSTEM",
        path="c:/temp/repo",
        root_path="c:/temp/repo",
        status="ONLINE",
        total_bytes=10000000
    )
    db.add(repo)
    db.commit()

    provider = ImmutabilityProvider(db)
    # Check default capabilities
    caps = provider.get_repository_capabilities(repo)
    assert caps["supports_soft_immutability"] is True
    assert caps["enforcement_level"] == "NONE"

    # Set soft-immutable
    set_res = provider.set_repository_immutability(repo.id, immutability_state="SOFT_IMMUTABLE", retention_days=60)
    assert set_res["success"] is True
    assert set_res["immutability_state"] == "SOFT_IMMUTABLE"
    assert set_res["protection_mode"] == "IMMUTABLE"
    assert set_res["capabilities"]["enforcement_level"] == "APPLICATION"

    # Local filesystem cannot claim OBJECT_LOCK; provider downgrades truthfully
    set_obj_lock = provider.set_repository_immutability(repo.id, immutability_state="OBJECT_LOCK")
    assert set_obj_lock["immutability_state"] == "SOFT_IMMUTABLE"

    db.close()


def test_fleet_policy_hierarchy_and_drift():
    db = SessionLocal()
    suffix = uuid.uuid4().hex[:6]

    # Global policy
    p_global = BackupPolicy(
        name=f"GlobalPolicy-{suffix}",
        backup_type="incremental",
        rpo_target_seconds=300,
        compression_enabled=True,
        encryption_enabled=True,
        is_active=True
    )
    # Group policy
    p_group = BackupPolicy(
        name=f"GroupPolicy-{suffix}",
        backup_type="full",
        rpo_target_seconds=60,
        compression_enabled=True,
        encryption_enabled=True,
        is_active=True
    )
    # Override policy
    p_override = BackupPolicy(
        name=f"OverridePolicy-{suffix}",
        backup_type="incremental",
        rpo_target_seconds=15,
        compression_enabled=False,
        encryption_enabled=True,
        is_active=True
    )
    db.add_all([p_global, p_group, p_override])
    db.commit()

    group = ClientGroup(name=f"FinanceFleet-{suffix}", policy_id=p_group.id)
    db.add(group)
    db.commit()

    client_m = Client(
        client_id=f"fleet-client-{suffix}",
        hostname=f"fleet-host-{suffix}",
        device_id=f"fleet-dev-{suffix}",
        os="Windows",
        ip_address="192.168.1.100",
        agent_version="8.0.0",
        status="active",
        group_id=group.id
    )
    db.add(client_m)
    db.commit()

    orchestrator = PolicyOrchestrator(db)

    # 1. Without client override, Group policy takes precedence over Global
    res1 = orchestrator.resolve_effective_policy(client_m.id)
    assert "GROUP" in res1["source"]
    assert res1["rpo_target_seconds"] == 60

    # 2. With temporary override, Override takes precedence over Group
    client_m.policy_override_id = p_override.id
    db.commit()
    res2 = orchestrator.resolve_effective_policy(client_m.id)
    assert res2["source"] == "TEMPORARY_OVERRIDE"
    assert res2["rpo_target_seconds"] == 15

    # 3. Simulate Dry-Run
    sim_diff = orchestrator.simulate_policy_dry_run(client_m.id, p_global.id)
    assert sim_diff["diff_count"] > 0
    assert "rpo_target_seconds" in sim_diff["differences"]

    # 4. Drift Detector
    drift_detector = DriftDetector(db)
    # Agent reports encryption is disabled, when policy requires enabled
    agent_report = {"compression_enabled": False, "encryption_enabled": False, "cpu_limit_percent": 10}
    drifts = drift_detector.detect_drift(client_m.id, agent_report)
    assert len(drifts) > 0
    assert any(d.drift_type == "ENCRYPTION_DISABLED" for d in drifts)

    db.close()


def test_security_incident_lifecycle():
    db = SessionLocal()
    suffix = uuid.uuid4().hex[:6]

    # Create incident
    from app.services.security.incident_manager import IncidentManager
    mgr = IncidentManager(db)
    inc = mgr.create_incident(title=f"Ransomware drill {suffix}", severity="HIGH", client_id=1)
    assert inc.status == "DETECTED"

    # Transition through states
    t1 = mgr.transition_status(inc.id, "CONFIRMED", notes="Triage confirmed encrypted files")
    assert t1["current_status"] == "CONFIRMED"

    t2 = mgr.transition_status(inc.id, "CONTAINED", notes="Network isolated")
    assert t2["current_status"] == "CONTAINED"

    t3 = mgr.transition_status(inc.id, "CLOSED", notes="Root cause remediated")
    assert t3["current_status"] == "CLOSED"

    db.refresh(inc)
    assert inc.closed_at is not None

    db.close()


def test_clean_recovery_point_discovery():
    db = SessionLocal()
    suffix = uuid.uuid4().hex[:6]

    cli = Client(
        client_id=f"cli-clean-{suffix}",
        hostname=f"host-clean-{suffix}",
        device_id=f"dev-clean-{suffix}",
        os="Windows",
        ip_address="192.168.1.111",
        agent_version="8.0.0",
        status="active"
    )
    db.add(cli)
    db.commit()

    job_clean = BackupJob(job_id=f"job-clean-{suffix}", client_id=cli.id, backup_type="full", status="completed")
    db.add(job_clean)
    db.commit()

    run_clean = BackupRun(job_id=job_clean.id, client_id=cli.id, backup_type="full", status="completed")
    db.add(run_clean)
    db.commit()

    # Create clean recovery point
    rp_clean = RecoveryPoint(
        client_id=cli.id,
        backup_run_id=run_clean.id,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
        status="valid",
        retention_status="active",
        protection_state="NORMAL"
    )
    db.add(rp_clean)
    db.commit()

    # Create suspected anomalous recovery point
    rp_held = RecoveryPoint(
        client_id=cli.id,
        backup_run_id=run_clean.id,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
        status="valid",
        retention_status="active",
        protection_state="SECURITY_HOLD"
    )
    db.add(rp_held)
    db.commit()

    selector = CleanRecoverySelector(db)
    points = selector.discover_clean_points(client_id=cli.id, limit=5)

    assert len(points) >= 2
    # Verify factual categorization
    clean_items = [p for p in points if p["recovery_point_id"] == rp_clean.id]
    held_items = [p for p in points if p["recovery_point_id"] == rp_held.id]

    assert clean_items[0]["risk_category"] == "VERIFIED_CLEAN"
    assert clean_items[0]["is_recommended"] is True
    assert held_items[0]["risk_category"] == "SUSPECTED_ANOMALOUS"

    db.close()


def test_safe_ransomware_simulation_drill():
    db = SessionLocal()
    engine = SimulationEngine(db)

    # Run non-destructive drill
    res = engine.run_simulation(scenario_type="RANSOMWARE_ENCRYPTION_BURST", file_count=10, encryption_ratio=0.8)

    assert res["detection_successful"] is True
    assert res["simulated_anomaly_score"] >= 60
    assert res["containment_action"] == "SECURITY_HOLD_TRIGGERED"
    assert res["encrypted_count"] == 8

    db.close()


def test_high_scale_scheduler_bounded_concurrency():
    db = SessionLocal()
    scheduler = HighScaleScheduler(db, max_concurrent_per_repo=2, max_concurrent_per_client=1)

    # Enqueue 3 tasks for client 10 and repo 5
    scheduler.enqueue_task("t1", "BACKUP", client_id=10, repository_id=5, priority=1)
    scheduler.enqueue_task("t2", "BACKUP", client_id=10, repository_id=5, priority=2)
    scheduler.enqueue_task("t3", "BACKUP", client_id=20, repository_id=5, priority=1)

    # First dispatch: client 10 limit is 1, so only t1 (priority 1) and t3 (client 20) dispatch
    dispatched = scheduler.dispatch_next_tasks()
    assert len(dispatched) == 2
    assert {d["task_id"] for d in dispatched} == {"t1", "t3"}

    # Repo 5 now has 2 active tasks (max limit reached). Attempting another dispatch yields 0
    scheduler.enqueue_task("t4", "BACKUP", client_id=30, repository_id=5, priority=1)
    d2 = scheduler.dispatch_next_tasks()
    assert len(d2) == 0

    # Complete t1
    scheduler.complete_task(client_id=10, repository_id=5)

    # Now repo 5 has 1 slot: t4 (priority 1) dispatches before t2 (priority 2)
    d3 = scheduler.dispatch_next_tasks()
    assert len(d3) == 1
    assert d3[0]["task_id"] == "t4"

    db.close()


def test_v8_rest_endpoints(auth_headers):
    # 1. Test Security Profiles Endpoint
    res_prof = client.get("/api/v1/security/profiles", headers=auth_headers)
    assert res_prof.status_code == 200
    assert len(res_prof.json()) >= 1

    # 2. Test Client Groups Endpoint
    res_grp = client.get("/api/v1/fleet/groups", headers=auth_headers)
    assert res_grp.status_code == 200

    # 3. Test Security Events Endpoint
    res_ev = client.get("/api/v1/security/events", headers=auth_headers)
    assert res_ev.status_code == 200

    # 4. Test Incidents Endpoint
    res_inc = client.get("/api/v1/incidents", headers=auth_headers)
    assert res_inc.status_code == 200

    # 5. Test Simulations Trigger Endpoint
    res_sim = client.post(
        "/api/v1/simulations/run",
        headers=auth_headers,
        json={"scenario_type": "RANSOMWARE_ENCRYPTION_BURST", "file_count": 6, "encryption_ratio": 0.6}
    )
    assert res_sim.status_code == 200
    assert res_sim.json()["detection_successful"] is True
