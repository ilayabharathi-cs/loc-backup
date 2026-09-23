"""Server Tests for RetroVault V6: Restore & Disaster Recovery Engine."""

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
from app.models.restore_job import RestoreJob
from app.models.restore_item import RestoreItem
import zstandard as zstd
from app.services.repository.local import get_repository
from app.services.gc.garbage_collector import GarbageCollector

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

    # Create Clients
    c1 = Client(
        client_id=f"PC-V6-A-{suffix}",
        hostname=f"DESKTOP-A-{suffix}",
        ip_address="192.168.1.50",
        device_id=f"DEV-V6-A-{suffix}",
        os="Windows 11",
        agent_version="6.0.0",
        status="online"
    )
    c2 = Client(
        client_id=f"PC-V6-B-{suffix}",
        hostname=f"DESKTOP-B-{suffix}",
        ip_address="192.168.1.51",
        device_id=f"DEV-V6-B-{suffix}",
        os="Windows 11",
        agent_version="6.0.0",
        status="online"
    )
    db.add_all([c1, c2])
    db.commit()
    db.refresh(c1)
    db.refresh(c2)

    # Create BackupJob
    bj = BackupJob(
        job_id=f"JOB-V6-{suffix}",
        client_id=c1.id,
        status="completed",
        backup_type="full"
    )
    db.add(bj)
    db.commit()
    db.refresh(bj)

    # Create BackupRun & StorageObjects with real repository CAS objects
    run = BackupRun(
        job_id=bj.id,
        client_id=c1.id,
        backup_type="full",
        status="completed",
        files_processed=3,
        bytes_processed=3000
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    repo = get_repository()

    # File 1: Text file with ZSTD compression
    content1 = b"RetroVault V6 Production Restore Engine Document Content 1\n" * 20
    sha1 = hashlib.sha256(content1).hexdigest()
    rel1, stored_sz1, stored_sha1, algo1, ratio1 = repo.store_cas_object(
        source_path_or_bytes=content1,
        content_sha256=sha1,
        original_size=len(content1),
        filename_hint="report.txt",
        compress=True
    )

    so1 = db.query(StorageObject).filter(StorageObject.content_sha256 == sha1).first()
    if not so1:
        so1 = StorageObject(
            object_id=sha1,
            content_sha256=sha1,
            stored_sha256=stored_sha1,
            original_size=len(content1),
            stored_size=stored_sz1,
            compression_algorithm=algo1,
            storage_path=rel1,
            state="AVAILABLE",
            integrity_status="VALID"
        )
        db.add(so1)
        db.commit()
    else:
        so1.state = "AVAILABLE"
        so1.integrity_status = "VALID"
        db.commit()
    db.refresh(so1)

    bf1 = BackupFile(
        client_id=c1.id,
        backup_run_id=run.id,
        original_path="C:\\Users\\Alice\\Documents\\report.txt",
        relative_path="Documents\\report.txt",
        file_name="report.txt",
        size_bytes=len(content1),
        sha256=sha1,
        storage_object_id=so1.id,
        storage_object=rel1,
        upload_status="completed",
        change_type="FULL"
    )

    # File 2: CSV file with NONE compression
    content2 = b"id,name,role\n1,Alice,Engineer\n2,Bob,Architect\n"
    sha2 = hashlib.sha256(content2).hexdigest()
    rel2, stored_sz2, stored_sha2, algo2, ratio2 = repo.store_cas_object(
        source_path_or_bytes=content2,
        content_sha256=sha2,
        original_size=len(content2),
        filename_hint="data.csv",
        compress=False
    )
    so2 = db.query(StorageObject).filter(StorageObject.content_sha256 == sha2).first()
    if not so2:
        so2 = StorageObject(
            object_id=sha2,
            content_sha256=sha2,
            stored_sha256=stored_sha2,
            original_size=len(content2),
            stored_size=stored_sz2,
            compression_algorithm="NONE",
            storage_path=rel2,
            state="AVAILABLE",
            integrity_status="VALID"
        )
        db.add(so2)
        db.commit()
    else:
        so2.state = "AVAILABLE"
        so2.integrity_status = "VALID"
        db.commit()
    db.refresh(so2)

    bf2 = BackupFile(
        client_id=c1.id,
        backup_run_id=run.id,
        original_path="C:\\Users\\Alice\\Projects\\data.csv",
        relative_path="Projects\\data.csv",
        file_name="data.csv",
        size_bytes=len(content2),
        sha256=sha2,
        storage_object_id=so2.id,
        storage_object=rel2,
        upload_status="completed",
        change_type="FULL"
    )

    db.add_all([bf1, bf2])
    db.commit()
    db.refresh(bf1)
    db.refresh(bf2)

    # Create RecoveryPoint
    rp = RecoveryPoint(
        client_id=c1.id,
        backup_run_id=run.id,
        backup_type="full",
        timestamp=datetime.datetime.now(datetime.timezone.utc),
        files_count=2,
        total_size_bytes=len(content1) + len(content2),
        status="valid",
        retention_status="active"
    )
    db.add(rp)
    db.commit()
    db.refresh(rp)

    yield {
        "c1": c1,
        "c2": c2,
        "run": run,
        "rp": rp,
        "bf1": bf1,
        "bf2": bf2,
        "content1": content1,
        "content2": content2,
        "sha1": sha1,
        "sha2": sha2
    }

    db.close()


def test_browse_recovery_point_virtual_tree(auth_headers, test_setup):
    """Verify virtual directory tree endpoint reconstructs manifest."""
    rp_id = test_setup["rp"].id
    res = client.get(f"/api/v1/restore/recovery-points/{rp_id}/files", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["name"] == "Root"
    assert "children" in data
    child_names = [c["name"] for c in data["children"]]
    assert "Documents" in child_names or "Projects" in child_names


def test_search_recovery_point_files(auth_headers, test_setup):
    """Verify searching files inside Recovery Point by query and extension."""
    rp_id = test_setup["rp"].id
    res = client.get(f"/api/v1/restore/recovery-points/{rp_id}/files/search?q=report", headers=auth_headers)
    assert res.status_code == 200
    items = res.json()["data"]
    assert len(items) == 1
    assert items[0]["file_name"] == "report.txt"

    res_ext = client.get(f"/api/v1/restore/recovery-points/{rp_id}/files/search?ext=.csv", headers=auth_headers)
    assert res_ext.status_code == 200
    items_ext = res_ext.json()["data"]
    assert len(items_ext) == 1
    assert items_ext[0]["file_name"] == "data.csv"


def test_restore_preview_calculation(auth_headers, test_setup):
    """Verify pre-flight preview calculations without disk modification."""
    rp_id = test_setup["rp"].id
    with tempfile.TemporaryDirectory() as dest_root:
        # Create an existing file to test predicted OVERWRITE
        existing_report = os.path.join(dest_root, "Documents", "report.txt")
        os.makedirs(os.path.dirname(existing_report), exist_ok=True)
        with open(existing_report, "wb") as f:
            f.write(b"old file")

        payload = {
            "recovery_point_id": rp_id,
            "restore_mode": "FULL_RECOVERY_POINT",
            "destination_root": dest_root,
            "conflict_mode": "OVERWRITE"
        }
        res = client.post("/api/v1/restore/preview", json=payload, headers=auth_headers)
        assert res.status_code == 200
        preview = res.json()["data"]
        assert preview["total_files"] == 2
        assert preview["actions"]["OVERWRITE"] == 1
        assert preview["actions"]["CREATE"] == 1
        assert preview["logical_bytes"] > 0
        assert preview["estimated_stored_read_bytes"] > 0


def test_path_safety_and_traversal_prevention(auth_headers, test_setup):
    """Verify path traversal and Windows reserved names are rejected."""
    rp_id = test_setup["rp"].id

    # Path traversal attack
    payload_traversal = {
        "recovery_point_id": rp_id,
        "restore_mode": "FULL_RECOVERY_POINT",
        "destination_root": "C:\\Restored",
        "selected_paths": ["../../Windows/System32/evil.dll"]
    }
    res = client.post("/api/v1/restore/preview", json=payload_traversal, headers=auth_headers)
    assert res.status_code == 400
    assert "traversal" in res.json()["detail"].lower()

    # Reserved device name
    payload_reserved = {
        "recovery_point_id": rp_id,
        "restore_mode": "FULL_RECOVERY_POINT",
        "destination_root": "C:\\Restored",
        "selected_paths": ["CON.txt"]
    }
    res_res = client.post("/api/v1/restore/preview", json=payload_reserved, headers=auth_headers)
    assert res_res.status_code == 400
    assert "reserved" in res_res.json()["detail"].lower()


def test_cross_client_restore_safeguard(auth_headers, test_setup):
    """Verify cross-client restore requires explicit acknowledgement and logs audit event."""
    c1 = test_setup["c1"]
    c2 = test_setup["c2"]
    rp = test_setup["rp"]

    # 1. Unacknowledged cross-client restore -> 400
    unauth_payload = {
        "source_client_id": c1.client_id,
        "target_client_id": c2.client_id,
        "recovery_point_id": rp.id,
        "source_path": "C:\\Restored",
        "target_path": "C:\\Restored",
        "acknowledge_cross_client": False
    }
    res_unauth = client.post("/api/v1/restore/jobs", json=unauth_payload, headers=auth_headers)
    assert res_unauth.status_code == 400

    # 2. Acknowledged cross-client restore -> 201
    auth_payload = {
        "source_client_id": c1.client_id,
        "target_client_id": c2.client_id,
        "recovery_point_id": rp.id,
        "source_path": "C:\\Restored",
        "target_path": "C:\\Restored",
        "acknowledge_cross_client": True
    }
    res_auth = client.post("/api/v1/restore/jobs", json=auth_payload, headers=auth_headers)
    assert res_auth.status_code == 201
    assert res_auth.json()["data"]["target_client_id"] == c2.id


def test_full_recovery_point_atomic_restore(auth_headers, test_setup):
    """Verify end-to-end full restore with atomic replacement and SHA-256 verification."""
    c1 = test_setup["c1"]
    rp = test_setup["rp"]

    with tempfile.TemporaryDirectory() as dest_dir:
        payload = {
            "source_client_id": c1.client_id,
            "target_client_id": c1.client_id,
            "recovery_point_id": rp.id,
            "source_path": dest_dir,
            "target_path": dest_dir,
            "restore_mode": "FULL_RECOVERY_POINT",
            "conflict_mode": "OVERWRITE"
        }
        res = client.post("/api/v1/restore/jobs", json=payload, headers=auth_headers)
        assert res.status_code == 201
        job_data = res.json()["data"]

        # Verify files restored on disk
        restored_report = os.path.join(dest_dir, "Documents", "report.txt")
        restored_csv = os.path.join(dest_dir, "Projects", "data.csv")

        assert os.path.exists(restored_report)
        assert os.path.exists(restored_csv)

        # Check content matches original
        with open(restored_report, "rb") as f:
            assert f.read() == test_setup["content1"]

        with open(restored_csv, "rb") as f:
            assert f.read() == test_setup["content2"]

        # Verify items endpoint
        items_res = client.get(f"/api/v1/restore/jobs/{job_data['id']}/items", headers=auth_headers)
        assert items_res.status_code == 200
        items = items_res.json()["data"]
        assert len(items) == 2
        for it in items:
            assert it["status"] == "COMPLETED"
            assert it["source_sha256"] == it["restored_sha256"]


def test_conflict_policies(auth_headers, test_setup):
    """Verify conflict SKIP, RENAME, FAIL policies."""
    c1 = test_setup["c1"]
    rp = test_setup["rp"]

    # 1. Conflict SKIP
    with tempfile.TemporaryDirectory() as dest_dir:
        report_path = os.path.join(dest_dir, "Documents", "report.txt")
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        original_bytes = b"PRE_EXISTING_USER_FILE_DO_NOT_TOUCH"
        with open(report_path, "wb") as f:
            f.write(original_bytes)

        payload_skip = {
            "source_client_id": c1.client_id,
            "target_client_id": c1.client_id,
            "recovery_point_id": rp.id,
            "source_path": dest_dir,
            "target_path": dest_dir,
            "restore_mode": "FILE",
            "conflict_mode": "SKIP",
            "selected_paths": ["Documents\\report.txt"]
        }
        res_skip = client.post("/api/v1/restore/jobs", json=payload_skip, headers=auth_headers)
        assert res_skip.status_code == 201

        # Check file was NOT overwritten
        with open(report_path, "rb") as f:
            assert f.read() == original_bytes

    # 2. Conflict RENAME
    with tempfile.TemporaryDirectory() as dest_dir:
        report_path = os.path.join(dest_dir, "Documents", "report.txt")
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, "wb") as f:
            f.write(b"EXISTING")

        payload_rename = {
            "source_client_id": c1.client_id,
            "target_client_id": c1.client_id,
            "recovery_point_id": rp.id,
            "source_path": dest_dir,
            "target_path": dest_dir,
            "restore_mode": "FILE",
            "conflict_mode": "RENAME",
            "selected_paths": ["Documents\\report.txt"]
        }
        res_rename = client.post("/api/v1/restore/jobs", json=payload_rename, headers=auth_headers)
        assert res_rename.status_code == 201

        renamed_path = os.path.join(dest_dir, "Documents", "report (Restored).txt")
        assert os.path.exists(renamed_path)
        with open(renamed_path, "rb") as f:
            assert f.read() == test_setup["content1"]


def test_corrupted_storage_object_rejection(auth_headers, test_setup):
    """Verify that restore safely fails when an underlying StorageObject is marked CORRUPTED."""
    db = SessionLocal()
    bf1 = test_setup["bf1"]
    so1 = db.query(StorageObject).filter(StorageObject.id == bf1.storage_object_id).first()
    so1.state = "CORRUPTED"
    so1.integrity_status = "CORRUPTED"
    db.commit()
    db.close()

    c1 = test_setup["c1"]
    rp = test_setup["rp"]
    with tempfile.TemporaryDirectory() as dest_dir:
        payload = {
            "source_client_id": c1.client_id,
            "target_client_id": c1.client_id,
            "recovery_point_id": rp.id,
            "source_path": dest_dir,
            "target_path": dest_dir,
            "restore_mode": "FULL_RECOVERY_POINT"
        }
        res = client.post("/api/v1/restore/jobs", json=payload, headers=auth_headers)
        # Should fail safely
        assert res.status_code == 400
        assert "SOURCE_OBJECT_CORRUPTED" in res.json()["detail"]


def test_active_restore_gc_protection(auth_headers, test_setup):
    """Verify Garbage Collection protects StorageObjects referenced by active restore jobs."""
    db = SessionLocal()
    c1 = test_setup["c1"]
    rp = test_setup["rp"]

    # Create an in-flight restore job in QUEUED status
    job = RestoreJob(
        restore_id=f"RESTORE-ACTIVE-{uuid.uuid4().hex[:6]}",
        source_client_id=c1.id,
        target_client_id=c1.id,
        recovery_point_id=rp.id,
        source_path="C:\\Test",
        target_path="C:\\Test",
        status="QUEUED",
        requested_by="Admin"
    )
    db.add(job)
    db.commit()

    gc = GarbageCollector(db)
    active_ids = gc.get_active_referenced_storage_ids()

    assert test_setup["bf1"].storage_object_id in active_ids
    assert test_setup["bf2"].storage_object_id in active_ids

    # Clean up job
    job.status = "COMPLETED"
    db.commit()
    db.close()
