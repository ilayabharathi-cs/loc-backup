"""Tests for V3 Incremental Backup Server APIs & Atomic Recovery Point Validation."""

import os
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database.session import get_db, SessionLocal
from app.models.client import Client
from app.models.backup_policy import BackupPolicy
from app.models.backup_run import BackupRun
from app.models.backup_file import BackupFile
from app.models.recovery_point import RecoveryPoint
from app.models.backup_job import BackupJob


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
def setup_client_and_policy(db):
    test_client = db.query(Client).filter(Client.client_id == "PC-V3-TEST").first()
    if not test_client:
        test_client = Client(
            client_id="PC-V3-TEST",
            hostname="WS-V3-NODE",
            device_id="DEV-V3-TEST-UUID",
            os="Windows 11 Pro",
            ip_address="192.168.1.100",
            agent_version="3.0.0",
            status="active"
        )
        db.add(test_client)
        db.commit()
        db.refresh(test_client)

    test_policy = db.query(BackupPolicy).filter(BackupPolicy.name == "V3 Incremental Test Policy").first()
    if not test_policy:
        test_policy = BackupPolicy(
            name="V3 Incremental Test Policy",
            description="Testing V3 incremental engine",
            is_active=True
        )
        db.add(test_policy)
        db.commit()
        db.refresh(test_policy)

    return test_client, test_policy


def test_incremental_run_creation(client, setup_client_and_policy):
    test_client, test_policy = setup_client_and_policy
    resp = client.post("/api/v1/backups/runs", json={
        "client_id": test_client.client_id,
        "policy_id": test_policy.id,
        "backup_type": "incremental",
        "baseline_run_id": None,
        "files_discovered": 10,
        "bytes_total": 2048
    })
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["backup_type"] == "incremental"
    assert data["files_discovered"] == 10
    assert data["bytes_total"] == 2048


def test_record_metadata_for_unchanged_and_deleted(client, setup_client_and_policy):
    test_client, test_policy = setup_client_and_policy
    # Create run
    r1 = client.post("/api/v1/backups/runs", json={
        "client_id": test_client.client_id,
        "policy_id": test_policy.id,
        "backup_type": "incremental"
    }).json()["data"]
    run_id = r1["id"]

    # Record metadata
    meta_payload = {
        "files": [
            {
                "original_path": "C:\\Data\\file_a.txt",
                "relative_path": "file_a.txt",
                "file_name": "file_a.txt",
                "size_bytes": 100,
                "sha256": "hash_a",
                "storage_object": "clients/PC-V3-TEST/runs/1/objects/hash_a",
                "change_type": "UNCHANGED",
                "upload_status": "completed"
            },
            {
                "original_path": "C:\\Data\\file_c.txt",
                "relative_path": "file_c.txt",
                "file_name": "file_c.txt",
                "size_bytes": 300,
                "sha256": "hash_c",
                "storage_object": None,
                "change_type": "DELETED",
                "upload_status": "deleted"
            }
        ]
    }
    rec_resp = client.post(
        f"/api/v1/backups/runs/{run_id}/record-metadata",
        headers={"X-Client-ID": test_client.client_id},
        json=meta_payload
    )
    assert rec_resp.status_code == 200
    files_recorded = rec_resp.json()["data"]
    assert len(files_recorded) == 2
    assert files_recorded[0]["change_type"] == "UNCHANGED"
    assert files_recorded[0]["storage_object"] == "clients/PC-V3-TEST/runs/1/objects/hash_a"
    assert files_recorded[1]["change_type"] == "DELETED"
    assert files_recorded[1]["upload_status"] == "deleted"
    assert files_recorded[1]["storage_object"] is None


def test_atomic_validation_rejects_missing_object_for_modified(client, setup_client_and_policy, db):
    """Rule 2 & 7: If a MODIFIED file is missing storage_object or failed, reject Recovery Point."""
    test_client, test_policy = setup_client_and_policy
    r1 = client.post("/api/v1/backups/runs", json={
        "client_id": test_client.client_id,
        "policy_id": test_policy.id,
        "backup_type": "incremental"
    }).json()["data"]
    run_id = r1["id"]

    # Insert an incomplete MODIFIED file (no storage_object)
    bad_file = BackupFile(
        client_id=test_client.id,
        original_path="C:\\Data\\b.txt",
        relative_path="b.txt",
        file_name="b.txt",
        size_bytes=250,
        sha256="hash_b2",
        backup_run_id=run_id,
        storage_object=None,  # Missing!
        change_type="MODIFIED",
        upload_status="failed"  # Marked failed!
    )
    db.add(bad_file)
    db.commit()

    # Attempt completion
    complete_resp = client.post(f"/api/v1/backups/runs/{run_id}/complete", json={
        "status": "completed",
        "files_uploaded": 0,
        "files_failed": 1,
        "bytes_uploaded": 0
    })
    assert complete_resp.status_code == 200
    # Run should not be fully completed
    assert complete_resp.json()["data"]["status"] in ("completed_with_warnings", "failed")

    # Verify NO Recovery Point was created
    pts = client.get(f"/api/v1/backups/recovery-points?client_id={test_client.client_id}").json()["data"]
    matching = [p for p in pts if p["backup_run_id"] == run_id]
    assert len(matching) == 0


def test_atomic_validation_rejects_missing_baseline_files(client, setup_client_and_policy, db):
    """Rule 5: If a baseline active file is completely absent from the run manifest, reject Recovery Point."""
    test_client, test_policy = setup_client_and_policy

    # Create Baseline Run 1
    base_run = BackupRun(
        job_id=1,
        client_id=test_client.id,
        policy_id=test_policy.id,
        backup_type="full",
        status="completed"
    )
    db.add(base_run)
    db.commit()
    db.refresh(base_run)

    # Add active files in baseline: file1 and file2
    f1 = BackupFile(
        client_id=test_client.id,
        original_path="C:\\Data\\f1.txt",
        relative_path="f1.txt",
        file_name="f1.txt",
        size_bytes=100,
        sha256="sha_1",
        storage_object="obj_1",
        backup_run_id=base_run.id,
        change_type="FULL",
        upload_status="completed"
    )
    f2 = BackupFile(
        client_id=test_client.id,
        original_path="C:\\Data\\f2.txt",
        relative_path="f2.txt",
        file_name="f2.txt",
        size_bytes=200,
        sha256="sha_2",
        storage_object="obj_2",
        backup_run_id=base_run.id,
        change_type="FULL",
        upload_status="completed"
    )
    db.add_all([f1, f2])
    db.commit()

    # Create Incremental Run 2 referencing Baseline Run 1
    inc_run = client.post("/api/v1/backups/runs", json={
        "client_id": test_client.client_id,
        "policy_id": test_policy.id,
        "backup_type": "incremental",
        "baseline_run_id": base_run.id
    }).json()["data"]
    inc_run_id = inc_run["id"]

    # Only register f1 in Incremental Run, but completely omit f2 (neither unchanged, modified, nor deleted!)
    client.post(
        f"/api/v1/backups/runs/{inc_run_id}/record-metadata",
        headers={"X-Client-ID": test_client.client_id},
        json={
            "files": [
                {
                    "original_path": "C:\\Data\\f1.txt",
                    "relative_path": "f1.txt",
                    "file_name": "f1.txt",
                    "size_bytes": 100,
                    "sha256": "sha_1",
                    "storage_object": "obj_1",
                    "change_type": "UNCHANGED",
                    "upload_status": "completed"
                }
            ]
        }
    )

    # Attempt to complete
    resp = client.post(f"/api/v1/backups/runs/{inc_run_id}/complete", json={
        "status": "completed",
        "files_uploaded": 0,
        "files_failed": 0,
        "bytes_uploaded": 0
    })
    assert resp.status_code == 200
    msg = resp.json()["message"]
    assert "skipped" in msg
    assert "missing" in msg.lower()

    # Ensure NO Recovery Point was created
    pts = client.get(f"/api/v1/backups/recovery-points?client_id={test_client.client_id}").json()["data"]
    matching = [p for p in pts if p["backup_run_id"] == inc_run_id]
    assert len(matching) == 0


def test_successful_incremental_run_creates_valid_recovery_point(client, setup_client_and_policy, db):
    """When all 7 rules pass, an incremental run produces a complete, valid Recovery Point."""
    test_client, test_policy = setup_client_and_policy

    # Baseline run
    base_run = BackupRun(
        job_id=2,
        client_id=test_client.id,
        policy_id=test_policy.id,
        backup_type="full",
        status="completed"
    )
    db.add(base_run)
    db.commit()
    db.refresh(base_run)

    f_base = BackupFile(
        client_id=test_client.id,
        original_path="C:\\Data\\doc.txt",
        relative_path="doc.txt",
        file_name="doc.txt",
        size_bytes=500,
        sha256="sha_doc",
        storage_object="obj_doc",
        backup_run_id=base_run.id,
        change_type="FULL",
        upload_status="completed"
    )
    db.add(f_base)
    db.commit()

    # Incremental run
    inc_run = client.post("/api/v1/backups/runs", json={
        "client_id": test_client.client_id,
        "policy_id": test_policy.id,
        "backup_type": "incremental",
        "baseline_run_id": base_run.id
    }).json()["data"]
    inc_run_id = inc_run["id"]

    # Register doc.txt as UNCHANGED referencing obj_doc, and new.txt as NEW
    client.post(
        f"/api/v1/backups/runs/{inc_run_id}/record-metadata",
        headers={"X-Client-ID": test_client.client_id},
        json={
            "files": [
                {
                    "original_path": "C:\\Data\\doc.txt",
                    "relative_path": "doc.txt",
                    "file_name": "doc.txt",
                    "size_bytes": 500,
                    "sha256": "sha_doc",
                    "storage_object": "obj_doc",
                    "change_type": "UNCHANGED",
                    "upload_status": "completed"
                },
                {
                    "original_path": "C:\\Data\\new.txt",
                    "relative_path": "new.txt",
                    "file_name": "new.txt",
                    "size_bytes": 250,
                    "sha256": "sha_new",
                    "storage_object": "obj_new",
                    "change_type": "NEW",
                    "upload_status": "completed"
                }
            ]
        }
    )

    # Complete
    complete_resp = client.post(f"/api/v1/backups/runs/{inc_run_id}/complete", json={
        "status": "completed",
        "files_uploaded": 1,
        "files_failed": 0,
        "bytes_uploaded": 250,
        "files_new": 1,
        "files_unchanged": 1
    })
    assert complete_resp.status_code == 200
    assert complete_resp.json()["data"]["status"] == "completed"

    # Recovery point created
    pts = client.get(f"/api/v1/backups/recovery-points?client_id={test_client.client_id}").json()["data"]
    matching = [p for p in pts if p["backup_run_id"] == inc_run_id]
    assert len(matching) == 1
    assert matching[0]["status"] == "valid"
    assert matching[0]["files_count"] == 2
    assert matching[0]["total_size_bytes"] == 750

    # Retrieve manifest
    manifest_resp = client.get(f"/api/v1/backups/recovery-points/{matching[0]['id']}/manifest")
    assert manifest_resp.status_code == 200
    m_data = manifest_resp.json()["data"]
    assert m_data["total_files"] == 2
    assert m_data["total_size_bytes"] == 750
    file_names = [f["file_name"] for f in m_data["files"]]
    assert "doc.txt" in file_names
    assert "new.txt" in file_names


def test_trigger_client_backup_with_incremental_type(client, setup_client_and_policy):
    test_client, test_policy = setup_client_and_policy
    resp = client.post(
        f"/api/v1/clients/{test_client.client_id}/backup",
        params={"backup_type": "incremental", "policy_id": test_policy.id}
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["backup_type"] == "incremental"
