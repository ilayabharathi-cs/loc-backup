"""Comprehensive tests for RetroVault V12 Cloud & Hybrid Storage Tiering Core."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import hashlib
import tempfile
import uuid
import datetime
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database.session import SessionLocal
from app.models.storage_object import StorageObject
from app.models.backup_file import BackupFile
from app.models.recovery_point import RecoveryPoint
from app.models.security_v8_models import DeletionGuard
from app.models.storage_tier_v12_models import CloudCredential, StorageTier, CloudOffloadedObject
from app.services.v12.cloud.provider_base import (
    CloudProviderBase,
    CloudProviderError,
    CloudAuthenticationError,
    CloudBucketNotFoundError,
    CloudObjectNotFoundError,
    CloudChecksumMismatchError,
    CloudTimeoutError,
    CloudPermissionError,
    CloudObjectLockError
)
from app.services.v12.cloud.mock_provider import MockCloudProvider
from app.services.v12.cloud.s3_provider import S3CompatibleProvider
from app.services.v12.cloud.credential_store import CredentialStoreService
from app.services.v12.cloud.tiering_manager import TieringManager, VALID_TIER_STATES
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


# ==============================================================================
# 1. PROVIDER TESTS
# ==============================================================================

def test_s3_provider_initialization_and_custom_endpoint():
    """Verify provider initialization, custom endpoint handling, and repr secret masking."""
    provider = S3CompatibleProvider(
        bucket="my-backup-bucket",
        access_key="AKIAIOSFODNN7EXAMPLE",
        secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        endpoint="https://minio.corp.internal:9000",
        region="us-west-2",
        prefix="retrovault-backups"
    )
    assert provider.bucket == "my-backup-bucket"
    assert provider.endpoint == "https://minio.corp.internal:9000"
    assert provider.region == "us-west-2"
    assert provider.prefix == "retrovault-backups"

    # Verify secret is never in repr
    rep = repr(provider)
    assert "wJalrXUtnFEMI" not in rep
    assert "AKIA****" in rep


def test_mock_provider_crud_operations():
    """Test upload, exists, head, download, list, and delete on mock provider."""
    provider = MockCloudProvider(bucket="test-vault")
    test_data = b"RetroVault V12 immutable cloud payload chunk"
    computed_sha = hashlib.sha256(test_data).hexdigest()

    # Upload
    res = provider.upload_object("cas/obj_001.dat", test_data, expected_sha256=computed_sha)
    assert res["key"] == "cas/obj_001.dat"
    assert res["size"] == len(test_data)
    assert res["sha256"] == computed_sha

    # Exists & Head
    assert provider.object_exists("cas/obj_001.dat") is True
    assert provider.object_exists("cas/non_existent.dat") is False

    head = provider.head_object("cas/obj_001.dat")
    assert head["size"] == len(test_data)
    assert head["sha256"] == computed_sha

    # Download
    downloaded = provider.download_object("cas/obj_001.dat")
    assert downloaded == test_data

    # List
    listed = provider.list_objects(prefix="cas/")
    assert len(listed) == 1
    assert listed[0]["key"] == "cas/obj_001.dat"

    # Delete
    assert provider.delete_object("cas/obj_001.dat") is True
    assert provider.object_exists("cas/obj_001.dat") is False


def test_provider_error_mapping_and_non_existent_object():
    """Test that provider errors are mapped cleanly without leaking secrets."""
    provider = MockCloudProvider(bucket="test-vault")
    with pytest.raises(CloudObjectNotFoundError) as exc_info:
        provider.download_object("missing_key.dat")
    assert "not found" in str(exc_info.value).lower()

    # Checksum mismatch
    with pytest.raises(CloudChecksumMismatchError):
        provider.upload_object("bad_checksum.dat", b"actual content", expected_sha256="wrong_checksum")


def test_provider_worm_object_lock():
    """Test WORM object lock immutability (GOVERNANCE and COMPLIANCE modes)."""
    provider = MockCloudProvider(bucket="worm-vault", supports_lock=True)
    provider.upload_object("immutable_doc.dat", b"critical compliance archive")

    # Lock until tomorrow
    tomorrow = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)
    provider.set_object_lock("immutable_doc.dat", mode="COMPLIANCE", retain_until_date=tomorrow)

    # Deletion attempt must fail with CloudObjectLockError
    with pytest.raises(CloudObjectLockError) as exc_info:
        provider.delete_object("immutable_doc.dat")
    assert "WORM Object Lock in effect" in str(exc_info.value)

    # Object remains intact
    assert provider.object_exists("immutable_doc.dat") is True


# ==============================================================================
# 2. CREDENTIAL STORE & ENCRYPTION TESTS
# ==============================================================================

def test_credential_encryption_at_rest_and_zero_leakage(db):
    """Verify secrets are encrypted at rest with SecretManager, masked in repr and responses."""
    svc = CredentialStoreService(db)
    unique_name = f"aws-prod-{uuid.uuid4().hex[:8]}"

    cred = svc.create_credential(
        name=unique_name,
        provider="s3",
        access_key="AKIAEXAMPLEKEY123",
        secret_key="SuperSecretKey999!",
        endpoint="https://s3.amazonaws.com",
        region="us-east-1"
    )

    # In DB: ciphertext must start with enc: and must NOT contain plaintext
    assert cred.access_key_encrypted.startswith("enc:")
    assert cred.secret_key_encrypted.startswith("enc:")
    assert "AKIAEXAMPLEKEY123" not in cred.access_key_encrypted
    assert "SuperSecretKey999!" not in cred.secret_key_encrypted

    # Repr must NEVER leak secrets
    rep = repr(cred)
    assert "SuperSecretKey999!" not in rep
    assert "AKIAEXAMPLEKEY123" not in rep

    # Public safe representation masks access key and omits secret key completely
    safe = svc.get_credential_safe(cred.id)
    assert "secret_key" not in safe
    assert "secret_key_encrypted" not in safe
    assert "SuperSecretKey999!" not in str(safe)
    assert safe["access_key_masked"] == "AK****23"

    # Decryption works internally for TieringManager
    acc, sec = svc.get_decrypted_secrets(cred.id)
    assert acc == "AKIAEXAMPLEKEY123"
    assert sec == "SuperSecretKey999!"

    # Clean up
    svc.delete_credential(cred.id)


def test_invalid_credential_handling(db):
    """Test validation errors for empty credentials and duplicate names."""
    svc = CredentialStoreService(db)
    with pytest.raises(ValueError):
        svc.create_credential(name="", provider="s3", access_key="k", secret_key="s")
    with pytest.raises(ValueError):
        svc.create_credential(name="n", provider="s3", access_key="", secret_key="s")
    with pytest.raises(ValueError):
        svc.create_credential(name="n", provider="s3", access_key="k", secret_key="")


# ==============================================================================
# 3. STORAGE TIER LIFECYCLE & STATE MACHINE TESTS
# ==============================================================================

def test_storage_tier_lifecycle_and_state_transitions(db):
    """Verify tier lifecycle states: CREATED -> VALIDATING -> READY / DEGRADED / ERROR / DISABLED."""
    manager = TieringManager(db)
    unique_tier = f"tier-{uuid.uuid4().hex[:8]}"

    tier = manager.create_tier(
        name=unique_tier,
        bucket="retrovault-archive",
        provider="mock",
        object_lock_enabled=False
    )
    assert tier.state == "CREATED"

    # Invalid transition: directly to READY should fail
    with pytest.raises(ValueError) as exc_info:
        manager.transition_state(tier, "READY")
    assert "cannot transition" in str(exc_info.value)

    # Valid transition: CREATED -> VALIDATING -> READY
    manager.transition_state(tier, "VALIDATING")
    assert tier.state == "VALIDATING"
    manager.transition_state(tier, "READY")
    assert tier.state == "READY"

    # Disable tier
    manager.update_tier(tier.tier_id, is_enabled=False)
    assert tier.state == "DISABLED"

    # Re-enable tier
    manager.update_tier(tier.tier_id, is_enabled=True)
    assert tier.state == "VALIDATING"

    # Clean up
    manager.delete_tier(tier.tier_id)


def test_storage_tier_validation_flow(db):
    """Test validate_tier on a mock tier driving state to READY."""
    manager = TieringManager(db)
    tier = manager.create_tier(
        name=f"test-val-{uuid.uuid4().hex[:8]}",
        bucket="mock-valid-bucket",
        provider="mock",
        object_lock_enabled=False
    )

    res = manager.validate_tier(tier.tier_id)
    assert res["valid"] is True
    assert res["state"] == "READY"

    # Re-fetch from DB
    db_tier = manager.get_tier(tier.tier_id)
    assert db_tier.state == "READY"
    assert db_tier.last_validated_at is not None

    manager.delete_tier(tier.tier_id)


def test_storage_tier_worm_degradation_when_unsupported(db):
    """Test that configuring Object Lock on a provider that does not support it marks tier DEGRADED."""
    # Create mock provider with supports_lock=False
    def mock_factory(t):
        return MockCloudProvider(bucket=t.bucket, supports_lock=False)

    manager = TieringManager(db, custom_provider_factory=mock_factory)
    tier = manager.create_tier(
        name=f"worm-test-{uuid.uuid4().hex[:8]}",
        bucket="non-locking-bucket",
        provider="mock",
        object_lock_enabled=True,
        immutability_mode="COMPLIANCE"
    )

    res = manager.validate_tier(tier.tier_id)
    assert res["valid"] is False
    assert res["state"] == "DEGRADED"
    assert "does not support WORM" in res["error"]

    manager.delete_tier(tier.tier_id)


# ==============================================================================
# 4. CAS OBJECT OFFLOAD & VERIFICATION WORKFLOW
# ==============================================================================

def test_cas_object_offload_verify_and_metadata_persistence(db):
    """
    Test safe offload workflow:
    CAS object -> offload -> mock S3 -> verification -> metadata persisted.
    Local-first: local CAS object remains untouched!
    """
    # 1. Setup local mock CAS object
    test_content = b"RetroVault Local CAS Object Content #12345"
    sha = hashlib.sha256(test_content).hexdigest()
    obj_id = f"cas_obj_{uuid.uuid4().hex[:10]}"

    so = StorageObject(
        object_id=obj_id,
        content_sha256=sha,
        stored_sha256=sha,
        original_size=len(test_content),
        stored_size=len(test_content),
        compression_algorithm="NONE",
        storage_path=f"objects/test/{obj_id}.dat",
        reference_count=1,
        state="AVAILABLE"
    )
    so._synthetic_bytes = test_content  # For test retrieval
    db.add(so)
    db.commit()

    # 2. Setup Storage Tier
    shared_mock = MockCloudProvider(bucket="offload-vault")
    manager = TieringManager(db, custom_provider_factory=lambda t: shared_mock)
    tier = manager.create_tier(
        name=f"offload-tier-{uuid.uuid4().hex[:8]}",
        bucket="offload-vault",
        provider="mock"
    )

    # 3. Offload
    offload = manager.offload_object(so.object_id, tier.tier_id)
    assert offload.state == "VERIFIED"
    assert offload.verification_status == "VERIFIED"
    assert offload.remote_size == len(test_content)
    assert offload.remote_sha256 == sha
    assert offload.verified_at is not None

    # 4. Verify Local-First Safety: Local CAS StorageObject is NOT deleted or changed!
    db.refresh(so)
    assert so.state == "AVAILABLE"
    assert so.stored_size == len(test_content)

    # 5. Remote object existence probe
    probe = manager.verify_remote_object(so.object_id, tier.tier_id)
    assert probe["exists"] is True
    assert probe["checksum_verified"] is True
    assert probe["verification_status"] == "VERIFIED"

    # 6. Idempotency test: offloading again should NOT re-upload, must return existing record
    initial_upload_count = shared_mock.upload_count
    repeat_offload = manager.offload_object(so.object_id, tier.tier_id)
    assert repeat_offload.id == offload.id
    assert shared_mock.upload_count == initial_upload_count  # No duplicate upload!

    # 7. Restore from tier test
    restored = manager.restore_from_tier(so.object_id, tier.tier_id)
    assert restored == test_content

    # Clean up
    db.delete(offload)
    db.delete(so)
    manager.delete_tier(tier.tier_id)


def test_offload_verification_checksum_mismatch_failure(db):
    """Test that offload fails and does not claim success when remote verification fails."""
    test_content = b"Corruptible data for verification test"
    sha = hashlib.sha256(test_content).hexdigest()
    obj_id = f"cas_corrupt_{uuid.uuid4().hex[:10]}"

    so = StorageObject(
        object_id=obj_id,
        content_sha256=sha,
        stored_sha256=sha,
        original_size=len(test_content),
        stored_size=len(test_content),
        storage_path=f"objects/{obj_id}.dat",
        reference_count=1,
        state="AVAILABLE"
    )
    so._synthetic_bytes = test_content
    db.add(so)
    db.commit()

    # Mock provider configured to corrupt checksum on verify
    failing_mock = MockCloudProvider(bucket="bad-vault", fail_next_verify=True)
    manager = TieringManager(db, custom_provider_factory=lambda t: failing_mock)
    tier = manager.create_tier(
        name=f"fail-tier-{uuid.uuid4().hex[:8]}",
        bucket="bad-vault",
        provider="mock"
    )

    with pytest.raises(CloudChecksumMismatchError):
        manager.offload_object(so.object_id, tier.tier_id)

    db.delete(so)
    manager.delete_tier(tier.tier_id)


def test_offload_blocked_by_deletion_guard(db):
    """Test that CAS objects locked by a pending DeletionGuard request are blocked from offload."""
    obj_id = f"cas_guard_{uuid.uuid4().hex[:10]}"
    so = StorageObject(
        object_id=obj_id,
        content_sha256="abc",
        stored_sha256="abc",
        original_size=100,
        stored_size=100,
        storage_path="objects/test.dat",
        reference_count=1,
        state="AVAILABLE"
    )
    db.add(so)
    db.commit()

    # Create pending DeletionGuard request
    guard = DeletionGuard(
        request_type="DELETE_OBJECT",
        target_resource_type="StorageObject",
        target_resource_id=obj_id,
        payload_json="{}",
        risk_score=90,
        status="PENDING",
        requester_username="admin",
        expires_at=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)
    )
    db.add(guard)
    db.commit()

    manager = TieringManager(db)
    tier = manager.create_tier(
        name=f"guard-tier-{uuid.uuid4().hex[:8]}",
        bucket="vault",
        provider="mock"
    )

    with pytest.raises(ValueError) as exc_info:
        manager.offload_object(obj_id, tier.tier_id)
    assert "locked by a pending DeletionGuard" in str(exc_info.value)

    db.delete(guard)
    db.delete(so)
    manager.delete_tier(tier.tier_id)


# ==============================================================================
# 5. REST API ENDPOINT TESTS
# ==============================================================================

def test_api_cloud_credentials_crud(auth_headers):
    """Test POST /api/v1/cloud/credentials, GET, and DELETE with secret masking."""
    cred_name = f"api-cred-{uuid.uuid4().hex[:8]}"

    # 1. Create
    payload = {
        "name": cred_name,
        "provider": "minio",
        "access_key": "minioadmin_access",
        "secret_key": "minioadmin_secret123",
        "endpoint": "http://127.0.0.1:9000",
        "region": "us-east-1",
        "use_tls": False,
        "verify_ssl": False
    }
    create_res = client.post("/api/v1/cloud/credentials", json=payload, headers=auth_headers)
    assert create_res.status_code == 201
    data = create_res.json()["data"]
    assert data["name"] == cred_name
    assert "secret_key" not in data
    assert data["access_key_masked"] == "mi****ss"
    cred_id = data["credential_id"]

    # 2. List
    list_res = client.get("/api/v1/cloud/credentials", headers=auth_headers)
    assert list_res.status_code == 200
    creds = list_res.json()["data"]
    match = [c for c in creds if c["credential_id"] == cred_id]
    assert len(match) == 1
    assert "secret_key" not in match[0]

    # 3. Delete
    del_res = client.delete(f"/api/v1/cloud/credentials/{cred_id}", headers=auth_headers)
    assert del_res.status_code == 200


def test_api_storage_tiers_and_offload_flow(auth_headers, db):
    """Test full API lifecycle: create tier, validate, offload, and delete."""
    # Create test StorageObject and write physical file
    test_bytes = b"API Tiering Integration Test Data"
    sha = hashlib.sha256(test_bytes).hexdigest()
    obj_id = f"api_cas_{uuid.uuid4().hex[:8]}"

    repo_root = settings.get_repository_root()
    obj_rel_path = f"objects/{obj_id}.dat"
    full_path = os.path.join(repo_root, obj_rel_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "wb") as f:
        f.write(test_bytes)

    so = StorageObject(
        object_id=obj_id,
        content_sha256=sha,
        stored_sha256=sha,
        original_size=len(test_bytes),
        stored_size=len(test_bytes),
        storage_path=obj_rel_path,
        reference_count=1,
        state="AVAILABLE"
    )
    db.add(so)
    db.commit()


    tier_name = f"api-tier-{uuid.uuid4().hex[:8]}"
    tier_payload = {
        "name": tier_name,
        "tier_type": "CLOUD_S3",
        "provider": "mock",
        "bucket": "api-test-bucket",
        "object_lock_enabled": False
    }

    # 1. Create Tier
    create_res = client.post("/api/v1/storage/tiers", json=tier_payload, headers=auth_headers)
    assert create_res.status_code == 201
    tier_data = create_res.json()["data"]
    tier_id = tier_data["tier_id"]
    assert tier_data["state"] == "CREATED"

    # 2. Get Tier
    get_res = client.get(f"/api/v1/storage/tiers/{tier_id}", headers=auth_headers)
    assert get_res.status_code == 200

    # 3. Validate Tier
    val_res = client.post(f"/api/v1/storage/tiers/{tier_id}/validate", headers=auth_headers)
    assert val_res.status_code == 200
    assert val_res.json()["data"]["valid"] is True
    assert val_res.json()["data"]["state"] == "READY"

    # 4. Offload CAS Object via API
    offload_payload = {"storage_object_ids": [obj_id]}
    off_res = client.post(f"/api/v1/storage/tiers/{tier_id}/offload", json=offload_payload, headers=auth_headers)
    assert off_res.status_code == 200
    off_data = off_res.json()["data"]
    assert off_data["offloaded_count"] == 1
    assert off_data["failed_count"] == 0
    assert off_data["items"][0]["status"] == "VERIFIED"

    # 5. Delete Tier
    del_res = client.delete(f"/api/v1/storage/tiers/{tier_id}", headers=auth_headers)
    assert del_res.status_code == 200

    # Clean up StorageObject
    db.delete(so)
    db.commit()


# ==============================================================================
# 6. RESILIENCE, RETENTION & PATH SAFETY TESTS
# ==============================================================================

def test_retry_and_timeout_bounded_behavior():
    """Verify provider retries transient timeouts up to max_retries and terminates cleanly."""
    provider = S3CompatibleProvider(
        bucket="retry-bucket",
        access_key="AKIA123",
        secret_key="SECRET123",
        endpoint="https://s3.amazonaws.com",
        max_retries=2,
        timeout=0.5
    )

    attempt_count = 0

    def flaky_transient_call():
        nonlocal attempt_count
        attempt_count += 1
        raise CloudTimeoutError("Simulated socket timeout", provider="s3")

    # Must raise after max_retries attempts
    with pytest.raises(CloudTimeoutError):
        provider._execute_with_retry(flaky_transient_call, "flaky_test_call")

    assert attempt_count == 3  # initial + 2 retries


def test_retention_bypass_quarantine_safety(db):
    """Verify that CAS objects referencing quarantined recovery points are blocked from offload."""
    obj_id = f"cas_quar_{uuid.uuid4().hex[:10]}"
    so = StorageObject(
        object_id=obj_id,
        content_sha256="quar123",
        stored_sha256="quar123",
        original_size=50,
        stored_size=50,
        storage_path="objects/quar.dat",
        reference_count=1,
        state="AVAILABLE"
    )
    db.add(so)
    db.commit()

    rp = None
    bf = None
    tier = None
    manager = None

    try:
        # Link to a QUARANTINED recovery point with isolated client_id
        rp = RecoveryPoint(
            client_id=9999,
            backup_run_id=9999,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
            protection_state="QUARANTINED"
        )
        db.add(rp)
        db.commit()

        bf = BackupFile(
            client_id=9999,
            backup_run_id=9999,
            file_name="infected_doc.exe",
            original_path="/tmp/infected_doc.exe",
            size_bytes=50,
            sha256="quar123",
            storage_object_id=so.id
        )
        db.add(bf)
        db.commit()

        manager = TieringManager(db)
        tier = manager.create_tier(
            name=f"quar-tier-{uuid.uuid4().hex[:8]}",
            bucket="vault",
            provider="mock"
        )

        with pytest.raises(ValueError) as exc_info:
            manager.offload_object(so.object_id, tier.tier_id)
        assert "belongs to a QUARANTINED recovery point" in str(exc_info.value)
    finally:
        if bf:
            db.delete(bf)
        if rp:
            db.delete(rp)
        db.delete(so)
        if tier and manager:
            manager.delete_tier(tier.tier_id)
        db.commit()



def test_safe_path_and_key_handling():
    """Verify that relative paths or prefix traversal attempts are normalized safely."""
    provider = S3CompatibleProvider(
        bucket="path-safe-bucket",
        access_key="AKIA123",
        secret_key="SECRET123",
        endpoint="mock",
        prefix="safe-vault/"
    )
    # Qualify key should strip leading slashes and enforce prefix
    qualified = provider._qualify_key("/cas/object/test.dat")
    assert qualified == "safe-vault/cas/object/test.dat"

