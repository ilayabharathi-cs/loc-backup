"""Comprehensive tests for RetroVault V12 Instant Virtual Recovery (40+ Scenarios)."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import hashlib
import tempfile
import uuid
import datetime
import pytest
from sqlalchemy import select
from fastapi.testclient import TestClient

from app.main import app
from app.database.session import SessionLocal
from app.models.client import Client
from app.models.backup_job import BackupJob
from app.models.backup_run import BackupRun
from app.models.backup_file import BackupFile
from app.models.recovery_point import RecoveryPoint
from app.models.storage_object import StorageObject
from app.models.storage_tier_v12_models import StorageTier
from app.models.virtual_recovery_v12_models import VirtualRecoverySession, VirtualRecoveryHydrationItem
from app.models.security_v8_models import DeletionGuard
from app.services.v12.virtual_recovery.provider_base import (
    VirtualRecoveryProviderBase,
    VirtualRecoveryError,
    SessionStateError,
    ObjectUnavailableError,
    IntegrityVerificationError,
    MountError,
    UnmountError
)
from app.services.v12.virtual_recovery.cache import BoundedLruCache
from app.services.v12.virtual_recovery.read_engine import ReadOnDemandEngine
from app.services.v12.virtual_recovery.hydrator import BackgroundHydrator
from app.services.v12.virtual_recovery.local_provider import LocalVirtualRecoveryProvider
from app.services.v12.virtual_recovery.session_manager import VirtualRecoverySessionManager
from app.services.v12.cloud.tiering_manager import TieringManager
from app.services.v12.cloud.mock_provider import MockCloudProvider
from app.services.retention.retention_engine import RetentionEngine
from app.config import settings

client = TestClient(app)


@pytest.fixture
def auth_headers():
    login_res = client.post("/api/v1/auth/login", json={"username": "admin", "password": "AdminPass123!"})
    assert login_res.status_code == 200
    token = login_res.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_env(db):
    """Sets up an isolated Client, BackupJob, BackupRun, StorageObject, BackupFile, and RecoveryPoint."""
    unique = uuid.uuid4().hex[:8]
    test_client = Client(
        client_id=f"cli-ivr-{unique}",
        hostname=f"host-{unique}",
        device_id=f"dev-{unique}",
        os="windows",
        ip_address="192.168.1.100",
        agent_version="12.0.0",
        status="active"
    )
    db.add(test_client)
    db.commit()

    job = BackupJob(
        job_id=f"job-ivr-{unique}",
        client_id=test_client.id,
        backup_type="full",
        status="completed"
    )
    db.add(job)
    db.commit()

    run = BackupRun(
        job_id=job.id,
        client_id=test_client.id,
        backup_type="full",
        status="completed",
        state="COMPLETED",
        started_at=datetime.datetime.now(datetime.timezone.utc),
        completed_at=datetime.datetime.now(datetime.timezone.utc)
    )
    db.add(run)
    db.commit()

    # Create 3 test files and CAS objects
    files_info = [
        ("boot/kernel.bin", b"VIRTUAL_KERNEL_BINARY_BOOT_DATA_001"),
        ("app/config.json", b'{"service":"core","database":"mssql","port":1433}'),
        ("data/database.mdf", b"MDF_DATABASE_BLOCK_DATA_" * 50)
    ]

    backup_files = []
    storage_objects = []

    repo_root = settings.get_repository_root()

    for rel_path, content in files_info:
        sha = hashlib.sha256(content).hexdigest()
        obj_id = f"ivr_obj_{uuid.uuid4().hex[:10]}"

        # Write actual file to repository root
        disk_path = os.path.join(repo_root, "objects", f"{obj_id}.dat")
        os.makedirs(os.path.dirname(disk_path), exist_ok=True)
        with open(disk_path, "wb") as f:
            f.write(content)

        so = StorageObject(
            object_id=obj_id,
            content_sha256=sha,
            stored_sha256=sha,
            original_size=len(content),
            stored_size=len(content),
            storage_path=f"objects/{obj_id}.dat",
            reference_count=1,
            state="AVAILABLE"
        )
        so._synthetic_bytes = content
        db.add(so)
        db.commit()
        storage_objects.append((so, disk_path))

        bf = BackupFile(
            client_id=test_client.id,
            backup_run_id=run.id,
            file_name=os.path.basename(rel_path),
            original_path=f"C:\\{rel_path.replace('/', '\\')}",
            relative_path=rel_path,
            size_bytes=len(content),
            sha256=sha,
            storage_object_id=so.id
        )
        db.add(bf)
        db.commit()
        backup_files.append(bf)

    rp = RecoveryPoint(
        client_id=test_client.id,
        backup_run_id=run.id,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
        files_count=len(files_info),
        total_size_bytes=sum(len(c) for _, c in files_info),
        status="valid",
        retention_status="active",
        protection_state="NORMAL"
    )
    db.add(rp)
    db.commit()

    yield {
        "client": test_client,
        "run": run,
        "rp": rp,
        "backup_files": backup_files,
        "storage_objects": storage_objects,
        "files_info": files_info
    }

    # Teardown
    try:
        # Remove any sessions referencing this rp
        sessions = db.scalars(select(VirtualRecoverySession).where(VirtualRecoverySession.recovery_point_id == rp.id)).all()
        for s in sessions:
            db.delete(s)
        db.commit()

        for _, disk_path in storage_objects:
            if os.path.exists(disk_path):
                try:
                    os.remove(disk_path)
                except OSError:
                    pass

        for bf in backup_files:
            db.delete(bf)
        for so, _ in storage_objects:
            db.delete(so)
        db.delete(rp)
        db.delete(run)
        db.delete(job)
        db.delete(test_client)
        db.commit()
    except Exception:
        pass


# ==============================================================================
# SUITE A: Session Lifecycle & State Machine (Scenarios 1-6)
# ==============================================================================

def test_01_session_creation_with_valid_rp(db, test_env):
    """Scenario 01: Create virtual recovery session for a valid Recovery Point."""
    manager = VirtualRecoverySessionManager(db)
    with tempfile.TemporaryDirectory() as target_dir:
        session = manager.create_session(
            recovery_point_id=test_env["rp"].id,
            target_path=target_dir
        )
        assert session.state == "CREATED"
        assert session.session_id.startswith("vrec_")
        assert session.recovery_point_id == test_env["rp"].id


def test_02_invalid_or_missing_rp_rejection(db):
    """Scenario 02: Attempting virtual recovery on a non-existent RP raises ValueError."""
    manager = VirtualRecoverySessionManager(db)
    with pytest.raises(ValueError) as exc:
        manager.create_session(recovery_point_id=9999999, target_path="/tmp/test")
    assert "not found" in str(exc.value).lower()


def test_03_quarantined_or_corrupted_rp_rejection(db, test_env):
    """Scenario 03: Recovery Point in QUARANTINED state must be rejected."""
    manager = VirtualRecoverySessionManager(db)
    rp = test_env["rp"]
    rp.protection_state = "QUARANTINED"
    db.commit()

    with pytest.raises(ValueError) as exc:
        manager.create_session(recovery_point_id=rp.id, target_path="/tmp/test")
    assert "cannot mount" in str(exc.value).lower()

    rp.protection_state = "NORMAL"
    db.commit()


def test_04_cross_client_isolation_rejection(db, test_env):
    """Scenario 04: Client ID mismatch without authorization is rejected."""
    manager = VirtualRecoverySessionManager(db)
    with pytest.raises(ValueError) as exc:
        manager.create_session(
            recovery_point_id=test_env["rp"].id,
            target_path="/tmp/test",
            client_id=test_env["client"].id + 999
        )
    assert "cross-client" in str(exc.value).lower()


def test_05_state_machine_permitted_transitions(db, test_env):
    """Scenario 05: Valid transitions CREATED -> PREPARING -> MOUNTING -> READY."""
    manager = VirtualRecoverySessionManager(db)
    with tempfile.TemporaryDirectory() as target_dir:
        session = manager.create_session(recovery_point_id=test_env["rp"].id, target_path=target_dir)
        assert session.state == "CREATED"
        manager.prepare_session(session.session_id)
        assert session.state == "PREPARING"
        manager.mount_session(session.session_id)
        assert session.state == "READY"


def test_06_invalid_state_transition_rejection(db, test_env):
    """Scenario 06: Invalid transition CREATED -> COMPLETED fails safely with SessionStateError."""
    manager = VirtualRecoverySessionManager(db)
    with tempfile.TemporaryDirectory() as target_dir:
        session = manager.create_session(recovery_point_id=test_env["rp"].id, target_path=target_dir)
        with pytest.raises(SessionStateError) as exc:
            manager.transition_state(session, "COMPLETED")
        assert "cannot transition" in str(exc.value).lower()


# ==============================================================================
# SUITE B: Virtual Mount & Read-On-Demand (Scenarios 7-15)
# ==============================================================================

def test_07_mount_filesystem_stubs_initialization(db, test_env):
    """Scenario 07: Mount creates directory hierarchy and stubs."""
    manager = VirtualRecoverySessionManager(db)
    with tempfile.TemporaryDirectory() as target_dir:
        session = manager.create_session(recovery_point_id=test_env["rp"].id, target_path=target_dir)
        manager.mount_session(session.session_id)

        # Check stubs exist
        assert os.path.exists(os.path.join(target_dir, "boot", "kernel.bin"))
        assert os.path.exists(os.path.join(target_dir, "app", "config.json"))
        assert os.path.exists(os.path.join(target_dir, "data", "database.mdf"))


def test_08_first_access_rto_telemetry(db, test_env):
    """Scenario 08: First on-demand read records TIME_TO_FIRST_ACCESS."""
    manager = VirtualRecoverySessionManager(db)
    with tempfile.TemporaryDirectory() as target_dir:
        session = manager.create_session(recovery_point_id=test_env["rp"].id, target_path=target_dir)
        manager.mount_session(session.session_id)
        assert session.time_to_first_access_ms is None

        # First read
        data = manager.read_logical_path(session.session_id, "boot/kernel.bin")
        assert len(data) > 0
        db.refresh(session)
        assert session.first_access_at is not None
        assert session.time_to_first_access_ms is not None
        assert session.time_to_first_access_ms >= 0


def test_09_read_on_demand_local_cas_resolution(db, test_env):
    """Scenario 09: Read-on-demand correctly retrieves bytes from local CAS StorageObject."""
    manager = VirtualRecoverySessionManager(db)
    with tempfile.TemporaryDirectory() as target_dir:
        session = manager.create_session(recovery_point_id=test_env["rp"].id, target_path=target_dir)
        manager.mount_session(session.session_id)

        data = manager.read_logical_path(session.session_id, "app/config.json")
        assert b'"service":"core"' in data


def test_10_read_on_demand_cloud_tier_fallback(db, test_env):
    """Scenario 10: If local CAS file is missing, fetch from configured cloud tier."""
    # Create mock tier
    cloud_mock = MockCloudProvider(bucket="cloud-backup-vault")
    tier_mgr = TieringManager(db, custom_provider_factory=lambda t: cloud_mock)
    tier = tier_mgr.create_tier(name=f"tier-vrec-{uuid.uuid4().hex[:6]}", bucket="cloud-backup-vault", provider="mock")

    # Offload the first file to the cloud tier
    so, disk_path = test_env["storage_objects"][0]
    tier_mgr.offload_object(so.object_id, tier.tier_id)

    # Now simulate local CAS deletion / loss
    if os.path.exists(disk_path):
        os.remove(disk_path)
    if hasattr(so, "_synthetic_bytes"):
        del so._synthetic_bytes

    # Create VirtualRecoverySession pointing to cloud_tier_id
    manager = VirtualRecoverySessionManager(db, tiering_manager=tier_mgr)
    with tempfile.TemporaryDirectory() as target_dir:
        session = manager.create_session(
            recovery_point_id=test_env["rp"].id,
            target_path=target_dir,
            cloud_tier_id=tier.id
        )
        manager.mount_session(session.session_id)

        # On-demand read should fall back to cloud tier
        data = manager.read_logical_path(session.session_id, "boot/kernel.bin")
        assert data == b"VIRTUAL_KERNEL_BINARY_BOOT_DATA_001"

    tier_mgr.delete_tier(tier.tier_id)


def test_11_checksum_verification_success(db, test_env):
    """Scenario 11: Checksum verification validates data matches expected SHA-256."""
    manager = VirtualRecoverySessionManager(db)
    with tempfile.TemporaryDirectory() as target_dir:
        session = manager.create_session(recovery_point_id=test_env["rp"].id, target_path=target_dir)
        manager.mount_session(session.session_id)
        data = manager.read_logical_path(session.session_id, "boot/kernel.bin")
        assert hashlib.sha256(data).hexdigest() == test_env["backup_files"][0].sha256


def test_12_checksum_verification_failure_on_corrupted_data(db, test_env):
    """Scenario 12: Corrupted local data triggers IntegrityVerificationError."""
    so, disk_path = test_env["storage_objects"][1]
    with open(disk_path, "wb") as f:
        f.write(b"CORRUPTED_TAMPERED_BYTES_123")

    manager = VirtualRecoverySessionManager(db)
    with tempfile.TemporaryDirectory() as target_dir:
        session = manager.create_session(recovery_point_id=test_env["rp"].id, target_path=target_dir)
        manager.mount_session(session.session_id)

        with pytest.raises(IntegrityVerificationError):
            manager.read_logical_path(session.session_id, "app/config.json")


def test_13_missing_object_error_handling(db, test_env):
    """Scenario 13: Querying a non-existent logical file raises ObjectUnavailableError."""
    manager = VirtualRecoverySessionManager(db)
    with tempfile.TemporaryDirectory() as target_dir:
        session = manager.create_session(recovery_point_id=test_env["rp"].id, target_path=target_dir)
        manager.mount_session(session.session_id)
        with pytest.raises(ObjectUnavailableError):
            manager.read_logical_path(session.session_id, "ghost/file.docx")


def test_14_read_slicing_with_offset_and_length(db, test_env):
    """Scenario 14: Slicing with offset and length returns accurate byte slice."""
    manager = VirtualRecoverySessionManager(db)
    with tempfile.TemporaryDirectory() as target_dir:
        session = manager.create_session(recovery_point_id=test_env["rp"].id, target_path=target_dir)
        manager.mount_session(session.session_id)
        # kernel.bin = b"VIRTUAL_KERNEL_BINARY_BOOT_DATA_001"
        slice_data = manager.read_logical_path(session.session_id, "boot/kernel.bin", offset=8, length=6)
        assert slice_data == b"KERNEL"


def test_15_out_of_bounds_offset_rejection(db, test_env):
    """Scenario 15: Out of bounds offset raises ValueError."""
    manager = VirtualRecoverySessionManager(db)
    with tempfile.TemporaryDirectory() as target_dir:
        session = manager.create_session(recovery_point_id=test_env["rp"].id, target_path=target_dir)
        manager.mount_session(session.session_id)
        with pytest.raises(ValueError):
            manager.read_logical_path(session.session_id, "boot/kernel.bin", offset=999999)


# ==============================================================================
# SUITE C: Bounded LRU Cache & Integrity (Scenarios 16-20)
# ==============================================================================

def test_16_cache_miss_triggers_fetch_and_caches_item(db, test_env):
    """Scenario 16: First read results in cache miss and caches item."""
    cache = BoundedLruCache(max_size_bytes=1024 * 1024)
    engine = ReadOnDemandEngine(db, cache=cache)
    provider = LocalVirtualRecoveryProvider(db)
    provider.read_engine = engine
    manager = VirtualRecoverySessionManager(db, provider=provider)

    with tempfile.TemporaryDirectory() as target_dir:
        session = manager.create_session(recovery_point_id=test_env["rp"].id, target_path=target_dir)
        manager.mount_session(session.session_id)
        assert cache.misses == 0
        assert cache.hits == 0

        engine.read_logical_path(session, "boot/kernel.bin")
        assert cache.misses == 1
        assert cache.hits == 0


def test_17_cache_hit_returns_cached_data_with_verification(db, test_env):
    """Scenario 17: Subsequent read is a cache hit."""
    cache = BoundedLruCache(max_size_bytes=1024 * 1024)
    engine = ReadOnDemandEngine(db, cache=cache)
    provider = LocalVirtualRecoveryProvider(db)
    provider.read_engine = engine
    manager = VirtualRecoverySessionManager(db, provider=provider)

    with tempfile.TemporaryDirectory() as target_dir:
        session = manager.create_session(recovery_point_id=test_env["rp"].id, target_path=target_dir)
        manager.mount_session(session.session_id)

        engine.read_logical_path(session, "boot/kernel.bin")
        assert cache.misses == 1

        engine.read_logical_path(session, "boot/kernel.bin")
        assert cache.hits == 1


def test_18_bounded_cache_eviction_when_size_exceeded():
    """Scenario 18: Inserting data past max_size_bytes evicts LRU items."""
    cache = BoundedLruCache(max_size_bytes=100)
    data1 = b"A" * 60
    data2 = b"B" * 60

    sha1 = hashlib.sha256(data1).hexdigest()
    sha2 = hashlib.sha256(data2).hexdigest()

    cache.put("sess1", "file1.dat", data1, sha1)
    assert cache.current_bytes == 60
    assert cache.evictions == 0

    # Adding data2 should evict file1.dat
    cache.put("sess1", "file2.dat", data2, sha2)
    assert cache.current_bytes == 60
    assert cache.evictions == 1
    assert cache.get("sess1", "file1.dat") is None


def test_19_cache_poisoning_detection():
    """Scenario 19: Tampering with cached bytes triggers IntegrityVerificationError."""
    cache = BoundedLruCache(max_size_bytes=1024)
    data = b"Clean Original Payload"
    sha = hashlib.sha256(data).hexdigest()
    cache.put("s1", "f1", data, sha)

    # Poison cache internal structure directly
    cache._cache[("s1", "f1")] = (b"Tampered Malware Payload", sha)

    with pytest.raises(IntegrityVerificationError):
        cache.get("s1", "f1")


def test_20_invalidate_session_cleans_only_target_session():
    """Scenario 20: Invalidate session removes only entries matching that session."""
    cache = BoundedLruCache(max_size_bytes=1024)
    cache.put("s1", "f1", b"data1", hashlib.sha256(b"data1").hexdigest())
    cache.put("s2", "f2", b"data2", hashlib.sha256(b"data2").hexdigest())

    assert len(cache._cache) == 2
    cache.invalidate_session("s1")
    assert len(cache._cache) == 1
    assert cache.get("s2", "f2") == b"data2"


# ==============================================================================
# SUITE D: Prefetch & Hydration Control (Scenarios 21-27)
# ==============================================================================

def test_21_controlled_prefetch_of_selected_files(db, test_env):
    """Scenario 21: Prefetch requested files into cache."""
    manager = VirtualRecoverySessionManager(db)
    with tempfile.TemporaryDirectory() as target_dir:
        session = manager.create_session(recovery_point_id=test_env["rp"].id, target_path=target_dir)
        manager.mount_session(session.session_id)

        res = manager.prefetch(session.session_id, ["boot/kernel.bin", "app/config.json"])
        assert res["prefetched_count"] == 2
        assert res["failed_count"] == 0


def test_22_prefetch_error_handling_for_missing_items(db, test_env):
    """Scenario 22: Prefetch records missing items cleanly in failed list."""
    manager = VirtualRecoverySessionManager(db)
    with tempfile.TemporaryDirectory() as target_dir:
        session = manager.create_session(recovery_point_id=test_env["rp"].id, target_path=target_dir)
        manager.mount_session(session.session_id)

        res = manager.prefetch(session.session_id, ["non_existent_boot.efi"])
        assert res["prefetched_count"] == 0
        assert res["failed_count"] == 1


def test_23_background_hydration_batch_processing(db, test_env):
    """Scenario 23: Hydrate batch writes physical files to target path."""
    manager = VirtualRecoverySessionManager(db)
    with tempfile.TemporaryDirectory() as target_dir:
        session = manager.create_session(recovery_point_id=test_env["rp"].id, target_path=target_dir)
        manager.mount_session(session.session_id)

        res = manager.hydrate(session.session_id, max_files=1)
        assert res["hydrated_count"] == 1
        assert session.hydrated_files == 1
        assert session.state in ["HYDRATING", "COMPLETED"]


def test_24_background_hydration_pause(db, test_env):
    """Scenario 24: Pausing hydration transitions state to PAUSED."""
    manager = VirtualRecoverySessionManager(db)
    with tempfile.TemporaryDirectory() as target_dir:
        session = manager.create_session(recovery_point_id=test_env["rp"].id, target_path=target_dir)
        manager.mount_session(session.session_id)
        manager.hydrate(session.session_id, max_files=1)

        pause_res = manager.pause_hydration(session.session_id)
        assert pause_res["state"] == "PAUSED"
        assert pause_res["hydration_status"] == "PAUSED"


def test_25_background_hydration_resume(db, test_env):
    """Scenario 25: Resuming hydration transitions state back to HYDRATING/COMPLETED."""
    manager = VirtualRecoverySessionManager(db)
    with tempfile.TemporaryDirectory() as target_dir:
        session = manager.create_session(recovery_point_id=test_env["rp"].id, target_path=target_dir)
        manager.mount_session(session.session_id)
        manager.hydrate(session.session_id, max_files=1)
        manager.pause_hydration(session.session_id)

        resume_res = manager.resume_hydration(session.session_id, max_files=1)
        assert resume_res["status"] in ["RUNNING", "COMPLETED"]


def test_26_full_hydration_completion_and_rto_metric(db, test_env):
    """Scenario 26: Complete hydration transitions session to COMPLETED and sets TIME_TO_FULL_HYDRATION."""
    manager = VirtualRecoverySessionManager(db)
    with tempfile.TemporaryDirectory() as target_dir:
        session = manager.create_session(recovery_point_id=test_env["rp"].id, target_path=target_dir)
        manager.mount_session(session.session_id)

        # Hydrate all 3 files
        manager.hydrate(session.session_id, max_files=10)
        db.refresh(session)
        assert session.state == "COMPLETED"
        assert session.hydration_status == "COMPLETED"
        assert session.hydrated_files == 3
        assert session.time_to_full_hydration_ms is not None
        assert session.time_to_full_hydration_ms >= 0


def test_27_hydration_speed_and_eta_calculation(db, test_env):
    """Scenario 27: Hydration calculates speed_bps and eta_seconds."""
    manager = VirtualRecoverySessionManager(db)
    with tempfile.TemporaryDirectory() as target_dir:
        session = manager.create_session(recovery_point_id=test_env["rp"].id, target_path=target_dir)
        manager.mount_session(session.session_id)

        res = manager.hydrate(session.session_id, max_files=1)
        assert "speed_bps" in res
        assert "eta_seconds" in res


# ==============================================================================
# SUITE E: Active Protection, Retention & GC Interaction (Scenarios 28-32)
# ==============================================================================

def test_28_active_virtual_recovery_protects_recovery_point(db, test_env):
    """Scenario 28: Active session sets RP protection_state to PROTECTED."""
    manager = VirtualRecoverySessionManager(db)
    rp = test_env["rp"]
    assert rp.protection_state == "NORMAL"

    with tempfile.TemporaryDirectory() as target_dir:
        session = manager.create_session(recovery_point_id=rp.id, target_path=target_dir)
        db.refresh(rp)
        assert rp.protection_state == "PROTECTED"
        assert "Active Instant Virtual Recovery" in rp.protected_reason


def test_29_retention_engine_does_not_expire_active_virtual_recovery_rp(db, test_env):
    """Scenario 29: RetentionEngine preserves active virtual recovery RP."""
    manager = VirtualRecoverySessionManager(db)
    rp = test_env["rp"]

    with tempfile.TemporaryDirectory() as target_dir:
        session = manager.create_session(recovery_point_id=rp.id, target_path=target_dir)

        # Run retention engine evaluation
        RetentionEngine.evaluate_policy(db)
        db.refresh(rp)

        # RP must remain active/protected
        assert rp.retention_status == "active"
        assert rp.protection_state == "PROTECTED"


def test_30_deletion_guard_blocks_virtual_recovery_on_pending_deletion(db, test_env):
    """Scenario 30: Pending DeletionGuard blocks virtual recovery session creation."""
    guard = DeletionGuard(
        request_type="DELETE_RECOVERY_POINT",
        target_resource_type="RecoveryPoint",
        target_resource_id=str(test_env["rp"].id),
        payload_json="{}",
        risk_score=95,
        status="PENDING",
        requester_username="admin",
        expires_at=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
    )
    db.add(guard)
    db.commit()

    manager = VirtualRecoverySessionManager(db)
    with pytest.raises(ValueError) as exc:
        manager.create_session(recovery_point_id=test_env["rp"].id, target_path="/tmp/test")
    assert "locked by a pending deletionguard" in str(exc.value).lower()

    db.delete(guard)
    db.commit()


def test_31_security_hold_preserves_recovery_point(db, test_env):
    """Scenario 31: RP under SECURITY_HOLD remains valid and accessible for virtual recovery."""
    rp = test_env["rp"]
    rp.protection_state = "SECURITY_HOLD"
    rp.security_hold_until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30)
    db.commit()

    manager = VirtualRecoverySessionManager(db)
    with tempfile.TemporaryDirectory() as target_dir:
        session = manager.create_session(recovery_point_id=rp.id, target_path=target_dir)
        assert session.state == "CREATED"


def test_32_unmount_safely_releases_protection(db, test_env):
    """Scenario 32: Unmounting releases RP protection back to NORMAL."""
    manager = VirtualRecoverySessionManager(db)
    rp = test_env["rp"]

    with tempfile.TemporaryDirectory() as target_dir:
        session = manager.create_session(recovery_point_id=rp.id, target_path=target_dir)
        manager.mount_session(session.session_id)
        db.refresh(rp)
        assert rp.protection_state == "PROTECTED"

        manager.unmount_session(session.session_id)
        db.refresh(rp)
        assert rp.protection_state == "NORMAL"
        assert rp.protected_reason is None


# ==============================================================================
# SUITE F: Workload Validation, DR & Security (Scenarios 33-42)
# ==============================================================================

def test_33_application_validation_with_workload(db, test_env):
    """Scenario 33: Application validation measures TIME_TO_APPLICATION_READY."""
    manager = VirtualRecoverySessionManager(db)
    with tempfile.TemporaryDirectory() as target_dir:
        session = manager.create_session(
            recovery_point_id=test_env["rp"].id,
            target_path=target_dir,
            workload_id="mssql-prod-01"
        )
        manager.mount_session(session.session_id)

        val = manager.validate_application(session.session_id)
        assert val["app_ready"] is True
        db.refresh(session)
        assert session.time_to_app_ready_ms is not None


def test_34_application_validation_failure_on_bad_mount(db, test_env):
    """Scenario 34: Validation failure when mount point is missing."""
    manager = VirtualRecoverySessionManager(db)
    with tempfile.TemporaryDirectory() as target_dir:
        session = manager.create_session(recovery_point_id=test_env["rp"].id, target_path=target_dir)
        session.mount_point = "/non_existent_mount_path_12345"
        val = manager.validate_application(session.session_id)
        assert val["app_ready"] is False


def test_35_dr_runbook_execution_flow_integration(db, test_env):
    """Scenario 35: DR Runbook flow (Preflight -> Session -> Mount -> App Validate -> Clean)."""
    manager = VirtualRecoverySessionManager(db)
    with tempfile.TemporaryDirectory() as target_dir:
        session = manager.create_session(recovery_point_id=test_env["rp"].id, target_path=target_dir)
        manager.prepare_session(session.session_id)
        manager.mount_session(session.session_id)
        app_val = manager.validate_application(session.session_id)
        assert app_val["app_ready"] is True
        manager.unmount_session(session.session_id)
        db.refresh(session)
        assert session.state == "UNMOUNTING"


def test_36_cross_client_access_blocked_without_admin(auth_headers, test_env):
    """Scenario 36: Cross-client virtual recovery forbidden via API."""
    payload = {
        "recovery_point_id": test_env["rp"].id,
        "target_path": "/tmp/test",
        "client_id": test_env["client"].id + 500
    }
    res = client.post("/api/v1/virtual-recovery/sessions", json=payload, headers=auth_headers)
    assert res.status_code == 400
    res_data = res.json()
    err_msg = res_data.get("detail") or res_data.get("error", {}).get("message", "")
    assert "cross-client" in err_msg.lower()


def test_37_path_traversal_attack_prevention(db, test_env):
    """Scenario 37: Path traversal attempt in target mount fails safely."""
    manager = VirtualRecoverySessionManager(db)
    session = manager.create_session(recovery_point_id=test_env["rp"].id, target_path="/tmp/ivr_test")
    # Simulate malicious relative path in hydration item
    item = VirtualRecoveryHydrationItem(
        session_id=session.id,
        relative_path="../../windows/system32/cmd.exe",
        size_bytes=100,
        sha256="abc",
        status="PENDING"
    )
    db.add(item)
    db.commit()

    hydrator = BackgroundHydrator(db)
    res = hydrator.hydrate_batch(session)
    db.refresh(item)
    assert item.status == "FAILED"
    assert "traversal" in item.error_message.lower()


def test_38_audit_log_trail(db, test_env):
    """Scenario 38: Audit log records session creation and unmount."""
    manager = VirtualRecoverySessionManager(db)
    with tempfile.TemporaryDirectory() as target_dir:
        session = manager.create_session(recovery_point_id=test_env["rp"].id, target_path=target_dir)
        manager.mount_session(session.session_id)
        manager.unmount_session(session.session_id)

        from app.models.audit_log import AuditLog
        logs = db.scalars(
            select(AuditLog).where(AuditLog.resource_id == session.session_id)
        ).all()
        actions = [l.action for l in logs]
        assert "VIRTUAL_RECOVERY_SESSION_CREATE" in actions
        assert "VIRTUAL_RECOVERY_SESSION_UNMOUNT" in actions


def test_39_api_full_flow(auth_headers, test_env):
    """Scenario 39: REST API Create -> Prepare -> Mount -> Prefetch -> Hydrate -> Unmount."""
    with tempfile.TemporaryDirectory() as target_dir:
        # Create
        c_res = client.post(
            "/api/v1/virtual-recovery/sessions",
            json={"recovery_point_id": test_env["rp"].id, "target_path": target_dir},
            headers=auth_headers
        )
        assert c_res.status_code == 201
        sid = c_res.json()["data"]["session_id"]

        # Prepare
        p_res = client.post(f"/api/v1/virtual-recovery/sessions/{sid}/prepare", headers=auth_headers)
        assert p_res.status_code == 200

        # Mount
        m_res = client.post(f"/api/v1/virtual-recovery/sessions/{sid}/mount", headers=auth_headers)
        assert m_res.status_code == 200

        # Prefetch
        pf_res = client.post(
            f"/api/v1/virtual-recovery/sessions/{sid}/prefetch",
            json={"paths": ["boot/kernel.bin"]},
            headers=auth_headers
        )
        assert pf_res.status_code == 200

        # Hydrate
        h_res = client.post(f"/api/v1/virtual-recovery/sessions/{sid}/hydrate", headers=auth_headers)
        assert h_res.status_code == 200

        # Unmount
        u_res = client.post(f"/api/v1/virtual-recovery/sessions/{sid}/unmount", headers=auth_headers)
        assert u_res.status_code == 200


def test_40_api_metrics_endpoint_returns_telemetry(auth_headers, test_env):
    """Scenario 40: GET /metrics endpoint returns RTO metrics and cache stats."""
    with tempfile.TemporaryDirectory() as target_dir:
        c_res = client.post(
            "/api/v1/virtual-recovery/sessions",
            json={"recovery_point_id": test_env["rp"].id, "target_path": target_dir},
            headers=auth_headers
        )
        sid = c_res.json()["data"]["session_id"]

        met_res = client.get(f"/api/v1/virtual-recovery/sessions/{sid}/metrics", headers=auth_headers)
        assert met_res.status_code == 200
        data = met_res.json()["data"]
        assert "time_to_first_access_ms" in data
        assert "time_to_app_ready_ms" in data
        assert "time_to_full_hydration_ms" in data
        assert "cache_hit_ratio" in data


def test_41_cancellation_terminates_session_and_frees_protection(db, test_env):
    """Scenario 41: Cancelling session transitions to UNMOUNTING and releases RP protection."""
    manager = VirtualRecoverySessionManager(db)
    rp = test_env["rp"]
    with tempfile.TemporaryDirectory() as target_dir:
        session = manager.create_session(recovery_point_id=rp.id, target_path=target_dir)
        manager.cancel_session(session.session_id)
        db.refresh(session)
        db.refresh(rp)
        assert session.state in ["CANCELLED", "UNMOUNTING"]
        assert rp.protection_state == "NORMAL"


def test_42_cloud_failure_fallback_error_handling(db, test_env):
    """Scenario 42: When both local CAS and cloud fail, fails with ObjectUnavailableError."""
    # Create tier with failing mock
    failing_cloud = MockCloudProvider(bucket="broken-vault", fail_next_upload="timeout")
    tier_mgr = TieringManager(db, custom_provider_factory=lambda t: failing_cloud)
    tier = tier_mgr.create_tier(name=f"broken-tier-{uuid.uuid4().hex[:6]}", bucket="broken-vault", provider="mock")

    # Remove local CAS file
    so, disk_path = test_env["storage_objects"][0]
    if os.path.exists(disk_path):
        os.remove(disk_path)
    if hasattr(so, "_synthetic_bytes"):
        del so._synthetic_bytes

    manager = VirtualRecoverySessionManager(db)
    with tempfile.TemporaryDirectory() as target_dir:
        session = manager.create_session(
            recovery_point_id=test_env["rp"].id,
            target_path=target_dir,
            cloud_tier_id=tier.id
        )
        manager.mount_session(session.session_id)

        with pytest.raises(ObjectUnavailableError):
            manager.read_logical_path(session.session_id, "boot/kernel.bin")

    tier_mgr.delete_tier(tier.tier_id)
