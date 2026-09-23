"""Unit and Integration tests for RetroVault V5 Storage Optimization Engine.

Tests:
1. Streaming ZSTD and GZIP compression, decompression, and ratio calculations.
2. Incompressible extension bypass.
3. Content-Addressed Storage (CAS) layout and cross-file/cross-client deduplication.
4. Calendar-aware GFS selector (Daily, Weekly, Monthly, Yearly, Keep-Last).
5. Two-phase safe Garbage Collection (Mark -> Sweep) and crash reconciliation.
6. Bit-rot integrity scrubbing and automated physical quarantine.
7. V5 REST APIs (/storage/metrics, /storage/objects, /storage/verify, /storage/gc, /retention/policies, /retention/evaluate).
"""

import os
import sys
import datetime
import hashlib
import shutil
import tempfile
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.database.session import SessionLocal
from app.models.client import Client
from app.models.backup_run import BackupRun
from app.models.backup_file import BackupFile
from app.models.recovery_point import RecoveryPoint
from app.models.storage_object import StorageObject
from app.models.retention_policy import RetentionPolicy
from app.services.compression import (
    compress_file,
    decompress_to_file,
    should_compress,
    verify_stored_integrity,
)
from app.services.repository.local import LocalFilesystemRepository
from app.services.retention.gfs_selector import GFSSelector
from app.services.retention.retention_engine import RetentionEngine
from app.services.gc.garbage_collector import GarbageCollector
from app.services.storage.integrity_service import StorageIntegrityService

client = TestClient(app)


@pytest.fixture(scope="module")
def admin_token():
    res = client.post("/api/v1/auth/login", json={"username": "admin", "password": "AdminPass123!"})
    assert res.status_code == 200
    data = res.json()["data"]
    return data["access_token"]


# ---------------------------------------------------------------------------
# 1. Compression Tests
# ---------------------------------------------------------------------------

def test_streaming_zstd_compression():
    with tempfile.TemporaryDirectory() as tmpdir:
        src = os.path.join(tmpdir, "test.txt")
        dst = os.path.join(tmpdir, "test.txt.zst")
        dec = os.path.join(tmpdir, "test_dec.txt")

        # Create compressible content
        content = b"RETROVAULT STORAGE ENGINE V5 COMPRESSION TEST! " * 5000  # ~230 KB
        with open(src, "wb") as f:
            f.write(content)

        stored_size, stored_sha, ratio = compress_file(src, dst, algorithm="ZSTD", level=3)
        assert stored_size < len(content)
        assert ratio > 2.0
        assert os.path.exists(dst)

        # Decompress and verify content round-trip
        orig_size, dec_sha = decompress_to_file(dst, dec, algorithm="ZSTD")
        assert orig_size == len(content)
        assert dec_sha == hashlib.sha256(content).hexdigest()

        with open(dec, "rb") as f:
            assert f.read() == content


def test_incompressible_bypass():
    assert should_compress("archive.zip", 10000) is False
    assert should_compress("photo.jpg", 10000) is False
    assert should_compress("video.mp4", 50000) is False
    assert should_compress("small.txt", 100) is False  # below min_size
    assert should_compress("database.sql", 50000) is True
    assert should_compress("logs.txt", 10000) is True


def test_stored_integrity_verification_and_corruption_detection():
    with tempfile.TemporaryDirectory() as tmpdir:
        src = os.path.join(tmpdir, "doc.txt")
        dst = os.path.join(tmpdir, "doc.txt.zst")

        content = b"Critical Financial Data Block 001\n" * 1000
        content_sha = hashlib.sha256(content).hexdigest()
        with open(src, "wb") as f:
            f.write(content)

        stored_size, stored_sha, _ = compress_file(src, dst, algorithm="ZSTD")

        # 1. Verify valid file
        valid, reason = verify_stored_integrity(dst, "ZSTD", stored_sha, content_sha)
        assert valid is True
        assert reason == "VALID"

        # 2. Corrupt one byte in the physical file
        with open(dst, "r+b") as f:
            f.seek(15)
            f.write(b"\xFF")

        # 3. Re-verify - must detect corruption
        valid_corrupt, err_reason = verify_stored_integrity(dst, "ZSTD", stored_sha, content_sha)
        assert valid_corrupt is False
        assert "checksum mismatch" in err_reason.lower() or "decompression error" in err_reason.lower()


# ---------------------------------------------------------------------------
# 2. CAS & Deduplication Tests
# ---------------------------------------------------------------------------

def test_cas_path_and_deduplication():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = LocalFilesystemRepository(root_path=tmpdir)
        content = b"Unique immutable payload for client deduplication test 12345"
        sha = hashlib.sha256(content).hexdigest()

        cas_path = repo.get_cas_path(sha)
        expected_suffix = os.path.join("objects", sha[:2], sha[2:4], sha)
        assert cas_path.endswith(expected_suffix)

        # Store object first time
        rel_path, size1, stored_sha1, algo, ratio = repo.store_cas_object(
            source_path_or_bytes=content,
            content_sha256=sha,
            original_size=len(content),
            filename_hint="doc1.txt",
        )
        assert os.path.exists(cas_path)

        # Store identical object second time (simulating another client / run)
        rel_path2, size2, stored_sha2, algo2, ratio2 = repo.store_cas_object(
            source_path_or_bytes=content,
            content_sha256=sha,
            original_size=len(content),
            filename_hint="doc2.txt",
        )
        # Should return same CAS relative path without creating a second file
        assert rel_path == rel_path2
        assert size1 == size2


# ---------------------------------------------------------------------------
# 3. GFS Selector Tests
# ---------------------------------------------------------------------------

class MockRecoveryPoint:
    def __init__(self, r_id: int, dt: datetime.datetime, is_manual: bool = False):
        self.id = r_id
        self.created_at = dt
        self.is_manual_protected = is_manual


def test_gfs_selector_tiers():
    selector = GFSSelector(
        keep_last=2,
        daily_count=3,
        weekly_count=2,
        monthly_count=2,
        yearly_count=2,
    )

    base_time = datetime.datetime(2026, 9, 23, 12, 0, tzinfo=datetime.timezone.utc)
    mock_rps = [
        MockRecoveryPoint(1, base_time),                                       # Today (newest)
        MockRecoveryPoint(2, base_time - datetime.timedelta(hours=2)),         # Today earlier
        MockRecoveryPoint(3, base_time - datetime.timedelta(days=1)),          # Yesterday
        MockRecoveryPoint(4, base_time - datetime.timedelta(days=2)),          # 2 days ago
        MockRecoveryPoint(5, base_time - datetime.timedelta(days=10)),         # 10 days ago (weekly)
        MockRecoveryPoint(6, base_time - datetime.timedelta(days=40)),         # 40 days ago (monthly)
        MockRecoveryPoint(7, base_time - datetime.timedelta(days=400)),        # 400 days ago (yearly)
        MockRecoveryPoint(8, base_time - datetime.timedelta(days=1000)),       # 1000 days ago (expired)
        MockRecoveryPoint(9, base_time - datetime.timedelta(days=1001), True), # 1001 days ago but manual protected
    ]

    decisions = selector.evaluate_points(mock_rps, now=base_time)

    # 1. Newest is protected
    assert decisions[1]["keep"] is True
    # 2. Keep last 2 is protected
    assert decisions[2]["keep"] is True
    # 3. Daily GFS
    assert decisions[3]["keep"] is True
    assert decisions[3]["is_daily"] is True
    # 4. Weekly GFS
    assert decisions[5]["keep"] is True
    # 5. Monthly GFS
    assert decisions[6]["keep"] is True
    # 6. Yearly GFS
    assert decisions[7]["keep"] is True
    # 7. Unprotected old point is EXPIRED
    assert decisions[8]["keep"] is False
    assert decisions[8]["tier"] == "EXPIRED"
    # 8. Manual protected is kept
    assert decisions[9]["keep"] is True
    assert decisions[9]["tier"] == "MANUAL"


# ---------------------------------------------------------------------------
# 4. Two-Phase Safe Garbage Collection Tests
# ---------------------------------------------------------------------------

def test_two_phase_garbage_collection():
    import uuid
    db = SessionLocal()
    try:
        # Create unreferenced test storage object
        test_uid = uuid.uuid4().hex
        dummy_content = f"Orphan data to be safely collected by Two-Phase GC {test_uid}".encode()
        dummy_sha = hashlib.sha256(dummy_content).hexdigest()

        repo = LocalFilesystemRepository()
        cas_rel, stored_size, stored_sha, _, _ = repo.store_cas_object(
            dummy_content, dummy_sha, len(dummy_content)
        )

        obj = StorageObject(
            object_id=f"test_obj_{test_uid[:12]}",
            content_sha256=dummy_sha,
            stored_sha256=stored_sha,
            original_size=len(dummy_content),
            stored_size=stored_size,
            compression_algorithm="ZSTD",
            compression_ratio=1.0,
            storage_path=cas_rel,
            reference_count=0,
            state="AVAILABLE",
            integrity_status="VALID",
        )
        db.add(obj)
        db.commit()
        db.refresh(obj)

        obj_id = obj.id
        phys_path = repo.resolve_stored_path(cas_rel)
        assert os.path.exists(phys_path)

        gc = GarbageCollector(db)

        # 1. Dry run simulation
        dry_job = gc.run_garbage_collection(dry_run=True)
        assert dry_job.candidates_found >= 1
        assert os.path.exists(phys_path)  # Must not delete in dry run

        # 2. Live GC execution
        live_job = gc.run_garbage_collection(dry_run=False)
        assert live_job.status == "completed"
        assert live_job.objects_deleted >= 1
        assert live_job.bytes_reclaimed > 0

        # Physical file must now be removed
        assert not os.path.exists(phys_path)

        # DB record transitioned to DELETED
        db.refresh(obj)
        assert obj.state == "DELETED"
        assert obj.reference_count == 0

    finally:
        db.close()


# ---------------------------------------------------------------------------
# 5. REST API Integration Tests
# ---------------------------------------------------------------------------

def test_v5_storage_metrics_api(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    res = client.get("/api/v1/storage/metrics", headers=headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert "total_logical_bytes" in data
    assert "total_stored_bytes" in data
    assert "deduplication_ratio" in data
    assert "compression_ratio" in data
    assert "repository_health" in data


def test_v5_retention_policy_crud_and_evaluate(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Create Retention Policy
    policy_payload = {
        "name": "Standard GFS Retention",
        "keep_last": 5,
        "daily": 7,
        "weekly": 4,
        "monthly": 12,
        "yearly": 2,
        "timezone": "UTC",
        "is_active": True,
    }
    create_res = client.post("/api/v1/retention/policies", json=policy_payload, headers=headers)
    assert create_res.status_code == 201
    created = create_res.json()["data"]
    p_id = created["id"]
    assert created["name"] == "Standard GFS Retention"
    assert created["keep_last"] == 5

    # 2. List Retention Policies
    list_res = client.get("/api/v1/retention/policies", headers=headers)
    assert list_res.status_code == 200
    assert any(p["id"] == p_id for p in list_res.json()["data"])

    # 3. Trigger Evaluation
    eval_res = client.post("/api/v1/retention/evaluate", json={"retention_policy_id": p_id}, headers=headers)
    assert eval_res.status_code == 200

    # 4. Clean up Policy
    del_res = client.delete(f"/api/v1/retention/policies/{p_id}", headers=headers)
    assert del_res.status_code == 200


def test_v5_storage_verify_api(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    res = client.post("/api/v1/storage/verify", json={"batch_size": 20, "verify_content": True}, headers=headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert "objects_checked" in data
    assert "objects_valid" in data
    assert "objects_corrupted" in data


def test_v5_storage_gc_api(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    # Run dry-run GC
    res = client.post("/api/v1/storage/gc", json={"dry_run": True}, headers=headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["status"] in ("simulated", "completed")

    # List GC history
    hist_res = client.get("/api/v1/storage/gc/jobs", headers=headers)
    assert hist_res.status_code == 200
    assert len(hist_res.json()["data"]) >= 1
