"""Unit and integration tests for RetroVault V4 Server Reliability APIs."""

import os
import sys
import hashlib
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.database.session import SessionLocal
from app.models.client import Client
from app.models.backup_policy import BackupPolicy
from app.models.backup_run import BackupRun


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def setup_v4_client(db):
    test_client = db.query(Client).filter(Client.client_id == "PC-V4-001").first()
    if not test_client:
        test_client = Client(
            client_id="PC-V4-001",
            hostname="TEST-V4-HOST",
            device_id="DEV-V4-TEST-UUID",
            os="Windows 11 Pro",
            ip_address="192.168.1.199",
            agent_version="4.0.0",
            status="approved"
        )
        db.add(test_client)
        db.commit()
        db.refresh(test_client)

    test_policy = db.query(BackupPolicy).filter(BackupPolicy.name == "V4 Reliability Policy").first()
    if not test_policy:
        test_policy = BackupPolicy(
            name="V4 Reliability Policy",
            is_active=True
        )
        db.add(test_policy)
        db.commit()
        db.refresh(test_policy)

    return test_client, test_policy


def test_upload_session_lifecycle_and_idempotent_chunks(client, setup_v4_client):
    test_client, test_policy = setup_v4_client

    # 1. Create a backup run
    run_resp = client.post("/api/v1/backups/runs", json={
        "client_id": test_client.client_id,
        "policy_id": test_policy.id,
        "backup_type": "full",
        "files_discovered": 1,
        "bytes_total": 8192
    })
    assert run_resp.status_code == 201
    run_data = run_resp.json()["data"]
    run_id = run_data["id"]
    assert run_data["state"] == "CREATED"
    assert run_data["lease_id"] is not None

    # 2. Create an upload session for a 2-chunk file (chunk size 4096)
    chunk_size = 4096
    total_size = 8000
    chunk0_data = b"A" * 4096
    chunk1_data = b"B" * (total_size - 4096)
    full_content = chunk0_data + chunk1_data
    full_sha = hashlib.sha256(full_content).hexdigest()

    sess_resp = client.post(f"/api/v1/backups/runs/{run_id}/upload-session", json={
        "file_path": "C:\\V4Data\\large_file.dat",
        "relative_path": "large_file.dat",
        "total_size": total_size,
        "chunk_size": chunk_size,
        "change_type": "FULL",
        "expected_sha256": full_sha
    })
    assert sess_resp.status_code == 201
    sess_data = sess_resp.json()["data"]
    session_id = sess_data["upload_session_id"]
    assert sess_data["total_chunks"] == 2
    assert sess_data["next_chunk_index"] == 0

    # 3. Test chunk SHA mismatch rejection
    bad_sha = "0000000000000000000000000000000000000000000000000000000000000000"
    bad_resp = client.put(
        f"/api/v1/backups/upload-session/{session_id}/chunks/0",
        content=chunk0_data,
        headers={"X-Chunk-SHA256": bad_sha}
    )
    assert bad_resp.status_code == 400
    err_msg = bad_resp.json().get("error", {}).get("message", "") or bad_resp.json().get("detail", "")
    assert "checksum mismatch" in err_msg.lower()

    # 4. Upload valid Chunk 0
    c0_sha = hashlib.sha256(chunk0_data).hexdigest()
    put0_resp = client.put(
        f"/api/v1/backups/upload-session/{session_id}/chunks/0",
        content=chunk0_data,
        headers={"X-Chunk-SHA256": c0_sha}
    )
    assert put0_resp.status_code == 200
    assert put0_resp.json()["data"]["status"] == "persisted"
    assert put0_resp.json()["data"]["already_existed"] is False

    # 5. Test chunk idempotency: send Chunk 0 again -> must succeed without duplicate bytes
    put0_dup = client.put(
        f"/api/v1/backups/upload-session/{session_id}/chunks/0",
        content=chunk0_data,
        headers={"X-Chunk-SHA256": c0_sha}
    )
    assert put0_dup.status_code == 200
    assert put0_dup.json()["data"]["already_existed"] is True

    # 6. Verify session status from server authority
    stat_resp = client.get(f"/api/v1/backups/upload-session/{session_id}/status")
    assert stat_resp.status_code == 200
    stat_data = stat_resp.json()["data"]
    assert 0 in stat_data["received_chunks"]
    assert stat_data["received_bytes"] == 4096
    assert stat_data["next_chunk_index"] == 1

    # 7. Upload Chunk 1
    c1_sha = hashlib.sha256(chunk1_data).hexdigest()
    put1_resp = client.put(
        f"/api/v1/backups/upload-session/{session_id}/chunks/1",
        content=chunk1_data,
        headers={"X-Chunk-SHA256": c1_sha}
    )
    assert put1_resp.status_code == 200
    assert put1_resp.json()["data"]["status"] == "persisted"

    # 8. Complete upload session
    comp_resp = client.post(f"/api/v1/backups/upload-session/{session_id}/complete", json={
        "final_sha256": full_sha,
        "total_size": total_size
    })
    assert comp_resp.status_code == 200
    comp_data = comp_resp.json()["data"]
    assert comp_data["sha256"] == full_sha
    assert comp_data["size_bytes"] == total_size
    assert comp_data["storage_object"] is not None

    # 9. Complete backup run and verify Recovery Point created
    complete_run = client.post(f"/api/v1/backups/runs/{run_id}/complete", json={
        "status": "completed",
        "files_uploaded": 1,
        "bytes_uploaded": total_size,
        "files_new": 1
    })
    assert complete_run.status_code == 200
    final_data = complete_run.json()["data"]
    assert final_data["status"] == "completed"
    assert final_data["state"] == "COMPLETED"


def test_run_state_lifecycle_and_checkpoints(client, setup_v4_client):
    test_client, test_policy = setup_v4_client

    # 1. Create run
    run_resp = client.post("/api/v1/backups/runs", json={
        "client_id": test_client.client_id,
        "policy_id": test_policy.id,
        "backup_type": "full"
    })
    run_id = run_resp.json()["data"]["id"]
    lease_id = run_resp.json()["data"]["lease_id"]

    # 2. Transition through state machine: DISCOVERING -> SCANNING -> BACKING_UP
    for st in ["DISCOVERING", "SCANNING", "BACKING_UP"]:
        resp = client.post(f"/api/v1/backups/runs/{run_id}/state", json={"state": st})
        assert resp.status_code == 200
        assert resp.json()["data"]["state"] == st

    # 3. Record a checkpoint
    cp_resp = client.post(f"/api/v1/backups/runs/{run_id}/checkpoint", json={
        "current_file": "C:\\V4Data\\in_progress.dat",
        "bytes_uploaded": 1048576,
        "last_chunk_index": 2,
        "state": "BACKING_UP",
        "checkpoint_version": 2
    })
    assert cp_resp.status_code == 200
    assert cp_resp.json()["data"]["current_file"] == "C:\\V4Data\\in_progress.dat"

    # 4. Simulate network loss -> interrupt
    intr_resp = client.post(f"/api/v1/backups/runs/{run_id}/interrupt")
    assert intr_resp.status_code == 200
    assert intr_resp.json()["data"]["state"] == "INTERRUPTED"
    assert intr_resp.json()["data"]["interrupted_at"] is not None

    # 5. Resume run
    res_resp = client.post(f"/api/v1/backups/runs/{run_id}/resume")
    assert res_resp.status_code == 200
    assert res_resp.json()["data"]["state"] == "RESUMING"
    assert res_resp.json()["data"]["resumed_at"] is not None

    # 6. Renew lease
    lease_resp = client.post(f"/api/v1/backups/runs/{run_id}/lease/renew", json={
        "lease_id": lease_id,
        "duration_seconds": 600
    })
    assert lease_resp.status_code == 200
    assert lease_resp.json()["data"]["is_valid"] is True

    # 7. Check audit run events
    events_resp = client.get(f"/api/v1/backups/runs/{run_id}/events")
    assert events_resp.status_code == 200
    events = events_resp.json()["data"]
    event_types = [e["event_type"] for e in events]
    assert "BACKUP_STARTED" in event_types
    assert "STATE_DISCOVERING" in event_types
    assert "CHECKPOINT_WRITTEN" in event_types
    assert "BACKUP_INTERRUPTED" in event_types
    assert "BACKUP_RESUMED" in event_types


def test_safe_concurrency_prevention(client, setup_v4_client):
    """Enforces prevention of simultaneous conflicting runs on the same client and policy."""
    test_client, test_policy = setup_v4_client

    # 1. Start a FULL run
    r1 = client.post("/api/v1/backups/runs", json={
        "client_id": test_client.client_id,
        "policy_id": test_policy.id,
        "backup_type": "full"
    })
    assert r1.status_code == 201

    # 2. Attempt to start an INCREMENTAL run simultaneously for the same client and policy -> must 409
    r2 = client.post("/api/v1/backups/runs", json={
        "client_id": test_client.client_id,
        "policy_id": test_policy.id,
        "backup_type": "incremental"
    })
    assert r2.status_code == 409
    err2 = r2.json().get("error", {}).get("message", "") or r2.json().get("detail", "")
    assert "simultaneous runs are prohibited" in err2.lower()

    # 3. Test explicit prevent_concurrent flag
    r3 = client.post("/api/v1/backups/runs", json={
        "client_id": test_client.client_id,
        "policy_id": test_policy.id,
        "backup_type": "full",
        "prevent_concurrent": True
    })
    assert r3.status_code == 409


def test_incomplete_upload_session_rejects_recovery_point(client, setup_v4_client):
    """Rule 6: If any upload session remains active/incomplete, Recovery Point creation must fail."""
    test_client, test_policy = setup_v4_client

    # 1. Start run
    r = client.post("/api/v1/backups/runs", json={
        "client_id": test_client.client_id,
        "policy_id": test_policy.id,
        "backup_type": "full",
        "files_discovered": 1
    })
    run_id = r.json()["data"]["id"]

    # 2. Create upload session and leave it incomplete (never call complete)
    client.post(f"/api/v1/backups/runs/{run_id}/upload-session", json={
        "file_path": "C:\\V4Data\\unfinished.dat",
        "total_size": 1000,
        "chunk_size": 1000
    })

    # 3. Attempt to complete run
    comp = client.post(f"/api/v1/backups/runs/{run_id}/complete", json={
        "status": "completed",
        "files_uploaded": 0,
        "bytes_uploaded": 0
    })
    assert comp.status_code == 200
    data = comp.json()["data"]
    assert data["state"] == "FAILED"
    assert "upload sessions remain active/incomplete" in data["error_message"]
