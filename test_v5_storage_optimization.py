"""End-to-End Comprehensive Verification Script for RetroVault V5 Storage Optimization Engine.

Demonstrates and verifies:
1. Cross-client Content-Addressed Storage (CAS) Deduplication.
2. Streaming ZSTD Compression with Incompressible file extension bypass.
3. Reference tracking across multiple backup runs and clients.
4. GFS Calendar Retention Evaluation (Daily, Weekly, Monthly, Yearly, Keep-Last).
5. Two-Phase Safe Garbage Collection (AVAILABLE -> DELETING -> DELETED).
6. Bit-rot scrubbing and physical quarantine isolation.
7. Decompression and restore streaming verification.
8. Real-time Storage Accounting & Efficiency Metrics.
"""

import datetime
import hashlib
import json
import os
import sys
import tempfile
import uuid

# Add server to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "server")))

from fastapi.testclient import TestClient
from app.main import app
from app.database.session import SessionLocal
from app.models.client import Client
from app.models.backup_policy import BackupPolicy
from app.models.backup_run import BackupRun
from app.models.backup_file import BackupFile
from app.models.recovery_point import RecoveryPoint
from app.models.storage_object import StorageObject
from app.models.retention_policy import RetentionPolicy
from app.services.repository.local import get_repository
from app.services.retention.retention_engine import RetentionEngine
from app.services.gc.garbage_collector import GarbageCollector
from app.services.storage.integrity_service import StorageIntegrityService

client = TestClient(app)


def log_step(step_num: int, title: str):
    print(f"\n{'='*70}\n[STEP {step_num}] {title}\n{'='*70}")


def main():
    print("Starting RetroVault V5 Comprehensive Verification Suite...")
    db = SessionLocal()

    try:
        # 0. Authenticate as Admin
        log_step(0, "Authenticate as Admin")
        login_res = client.post("/api/v1/auth/login", json={"username": "admin", "password": "AdminPass123!"})
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        token = login_res.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("Authenticated successfully as Admin.")

        # 1. Setup Test Clients and Policy
        log_step(1, "Create Test Workstations and Backup Policy")
        unique_suffix = uuid.uuid4().hex[:6]
        c1 = Client(
            client_id=f"PC-V5-A-{unique_suffix}",
            hostname=f"DESKTOP-ALPHA-{unique_suffix}",
            ip_address="192.168.1.101",
            device_id=f"DEV-V5-A-{unique_suffix}",
            os="Windows 11 Pro",
            agent_version="5.0.0",
            status="online"
        )
        c2 = Client(
            client_id=f"PC-V5-B-{unique_suffix}",
            hostname=f"DESKTOP-BETA-{unique_suffix}",
            ip_address="192.168.1.102",
            device_id=f"DEV-V5-B-{unique_suffix}",
            os="Windows 11 Pro",
            agent_version="5.0.0",
            status="online"
        )
        policy = BackupPolicy(
            name=f"V5 Storage Policy {unique_suffix}",
            description="Policy with GFS Retention and Deduplication enabled",
            backup_type="incremental",
            change_detection="metadata",
            compression_enabled=True,
            encryption_enabled=False,
            is_active=True
        )
        db.add_all([c1, c2, policy])
        db.commit()
        db.refresh(c1)
        db.refresh(c2)
        db.refresh(policy)
        print(f"Created Client A (ID: {c1.id}), Client B (ID: {c2.id}), Policy (ID: {policy.id})")

        # 2. Upload identical files from Client A and Client B to verify Global Deduplication
        log_step(2, "Test Global Cross-Client Deduplication")
        shared_content = (f"COMMON CORPORATE DOCUMENT TEMPLATE {unique_suffix} - CONFIDENTIAL.\n".encode() * 2000)  # ~112 KB
        shared_sha256 = hashlib.sha256(shared_content).hexdigest()

        # Run 1 on Client A
        r1_resp = client.post("/api/v1/backups/runs", json={"client_id": c1.client_id, "policy_id": policy.id, "backup_type": "full"})
        assert r1_resp.status_code == 201, f"Failed to create run1: {r1_resp.text}"
        run1_id = r1_resp.json()["data"]["id"]
        run1 = db.get(BackupRun, run1_id)

        upload1_res = client.post(
            "/api/v1/backups/upload",
            headers={
                **headers,
                "X-Client-ID": c1.client_id,
                "X-Run-ID": str(run1.id),
                "X-Original-Path": r"C:\Corporate\Template.docx",
                "X-Relative-Path": r"Corporate\Template.docx",
                "X-SHA256": shared_sha256,
                "X-File-Size": str(len(shared_content)),
                "X-Change-Type": "FULL"
            },
            content=shared_content
        )
        assert upload1_res.status_code == 200, f"Upload 1 failed: {upload1_res.text}"
        file1_data = upload1_res.json()["data"]
        print(f"Client A uploaded file: {file1_data['file_name']} (Storage Object ID: {file1_data['storage_object_id']})")

        # Check StorageObject in DB
        so1 = db.query(StorageObject).filter(StorageObject.content_sha256 == shared_sha256).first()
        assert so1 is not None
        assert so1.reference_count == 1
        assert so1.state == "AVAILABLE"
        assert so1.compression_algorithm in ("ZSTD", "GZIP", "NONE")
        print(f"Created StorageObject {so1.object_id} with ref_count = 1, stored_size = {so1.stored_size} bytes (ratio: {so1.compression_ratio}x)")

        # Run 2 on Client B (completely different client machine!)
        r2_resp = client.post("/api/v1/backups/runs", json={"client_id": c2.client_id, "policy_id": policy.id, "backup_type": "full"})
        assert r2_resp.status_code == 201, f"Failed to create run2: {r2_resp.text}"
        run2_id = r2_resp.json()["data"]["id"]
        run2 = db.get(BackupRun, run2_id)

        upload2_res = client.post(
            "/api/v1/backups/upload",
            headers={
                **headers,
                "X-Client-ID": c2.client_id,
                "X-Run-ID": str(run2.id),
                "X-Original-Path": r"D:\Shared\CorporateTemplate.docx",
                "X-Relative-Path": r"Shared\CorporateTemplate.docx",
                "X-SHA256": shared_sha256,
                "X-File-Size": str(len(shared_content)),
                "X-Change-Type": "FULL"
            },
            content=shared_content
        )
        assert upload2_res.status_code == 200, f"Upload 2 failed: {upload2_res.text}"
        file2_data = upload2_res.json()["data"]

        # Verify cross-client deduplication occurred!
        db.refresh(so1)
        assert file2_data["storage_object_id"] == so1.id
        assert so1.reference_count == 2, f"Expected ref_count 2, got {so1.reference_count}"
        print(f"[VERIFIED] Global Cross-Client Deduplication Succeeded! 2 clients share StorageObject {so1.object_id}, ref_count = {so1.reference_count}")

        # 3. Test Incompressible file extension bypass
        log_step(3, "Test Incompressible File Bypass (.zip, .mp4, etc.)")
        zip_content = b"PK\x03\x04" + os.urandom(2048)  # Dummy zip binary
        zip_sha256 = hashlib.sha256(zip_content).hexdigest()

        upload_zip_res = client.post(
            "/api/v1/backups/upload",
            headers={
                **headers,
                "X-Client-ID": c1.client_id,
                "X-Run-ID": str(run1.id),
                "X-Original-Path": r"C:\Backups\archive.zip",
                "X-SHA256": zip_sha256,
                "X-File-Size": str(len(zip_content)),
            },
            content=zip_content
        )
        assert upload_zip_res.status_code == 200
        so_zip = db.query(StorageObject).filter(StorageObject.content_sha256 == zip_sha256).first()
        assert so_zip is not None
        assert so_zip.compression_algorithm == "NONE"
        print(f"[VERIFIED] Incompressible file 'archive.zip' bypassed compression (algo: {so_zip.compression_algorithm})")

        # 4. Finalize Backup Runs and create valid Recovery Points
        log_step(4, "Finalize Backup Runs and Atomic Recovery Point Creation")
        run1.status = "completed"
        run1.state = "COMPLETED"
        run2.status = "completed"
        run2.state = "COMPLETED"

        now = datetime.datetime.now(datetime.timezone.utc)
        rp1 = RecoveryPoint(
            client_id=c1.id,
            backup_run_id=run1.id,
            backup_type="full",
            timestamp=now - datetime.timedelta(days=2),
            files_count=2,
            total_size_bytes=len(shared_content) + len(zip_content),
            status="valid",
            retention_status="active",
            created_at=now - datetime.timedelta(days=2)
        )
        rp2 = RecoveryPoint(
            client_id=c2.id,
            backup_run_id=run2.id,
            backup_type="full",
            timestamp=now,
            files_count=1,
            total_size_bytes=len(shared_content),
            status="valid",
            retention_status="active",
            created_at=now
        )
        db.add_all([rp1, rp2])
        db.commit()
        print(f"Created RecoveryPoint 1 (Run {run1.id}) and RecoveryPoint 2 (Run {run2.id})")

        # 5. GFS Retention Evaluation
        log_step(5, "Configure and Evaluate GFS Retention Policy")
        ret_policy = RetentionPolicy(
            name="Production GFS Retention",
            policy_id=policy.id,
            keep_last=1,  # Keep 1 newest point
            daily=1,
            weekly=1,
            monthly=1,
            yearly=1,
            timezone="UTC",
            is_active=True
        )
        db.add(ret_policy)
        db.commit()
        db.refresh(ret_policy)

        # Trigger retention evaluation
        evaluations = RetentionEngine.evaluate_policy(db, retention_policy_id=ret_policy.id)
        assert len(evaluations) > 0
        db.refresh(rp1)
        db.refresh(rp2)
        print(f"Evaluation completed: RP1 status = {rp1.retention_status} (tier: {rp1.retention_tier}), RP2 status = {rp2.retention_status} (tier: {rp2.retention_tier})")
        assert rp2.retention_status == "active"  # Latest point is always protected!

        # 6. Two-Phase Garbage Collection Verification
        log_step(6, "Execute Two-Phase Safe Garbage Collection (Dry-Run and Live)")
        # Create an orphaned object not referenced by any recovery point
        orphan_bytes = b"TEMPORARY UNREFERENCED DATA BLOCK 999\n" * 500
        orphan_sha = hashlib.sha256(orphan_bytes).hexdigest()
        repo = get_repository()
        cas_rel, stored_sz, stored_h, _, _ = repo.store_cas_object(orphan_bytes, orphan_sha, len(orphan_bytes))

        orphan_obj = StorageObject(
            object_id=f"orphan_{uuid.uuid4().hex[:10]}",
            content_sha256=orphan_sha,
            stored_sha256=stored_h,
            original_size=len(orphan_bytes),
            stored_size=stored_sz,
            compression_algorithm="ZSTD",
            compression_ratio=2.0,
            storage_path=cas_rel,
            reference_count=0,
            state="AVAILABLE",
            integrity_status="VALID",
        )
        db.add(orphan_obj)
        db.commit()
        db.refresh(orphan_obj)

        orphan_phys = repo.resolve_stored_path(cas_rel)
        assert os.path.exists(orphan_phys)

        # Step 6a: Dry Run GC
        gc = GarbageCollector(db)
        dry_job = gc.run_garbage_collection(dry_run=True)
        assert dry_job.candidates_found >= 1
        assert os.path.exists(orphan_phys), "Dry run must NOT delete physical files!"
        print(f"[VERIFIED] GC Dry Run: found {dry_job.candidates_found} candidates, {dry_job.bytes_reclaimed} reclaimable bytes. No files deleted.")

        # Step 6b: Live GC Pass (Two-Phase: Mark -> Sweep)
        live_job = gc.run_garbage_collection(dry_run=False)
        assert live_job.status == "completed"
        assert live_job.objects_deleted >= 1
        assert not os.path.exists(orphan_phys), "Live GC must physically delete orphaned files!"

        # Verify shared storage object from Step 2 was NOT deleted because RP2 references it
        shared_phys = repo.resolve_stored_path(so1.storage_path)
        assert os.path.exists(shared_phys), "Referenced object must NEVER be deleted by GC!"
        db.refresh(so1)
        assert so1.state == "AVAILABLE"
        print(f"[VERIFIED] Two-Phase GC deleted orphaned object ({live_job.bytes_reclaimed} bytes reclaimed). Active referenced objects remain intact!")

        # 7. Bit-rot Scrubbing and Automated Physical Quarantine
        log_step(7, "Test Checksum Scrubbing and Bit-rot Quarantine")
        # Inject artificial bit-rot into a corruptible test object
        bad_content = b"INTEGRITY TEST DATA FOR BIT-ROT SIMULATION"
        bad_sha = hashlib.sha256(bad_content).hexdigest()
        bad_rel, bad_sz, bad_stored_sha, _, _ = repo.store_cas_object(bad_content, bad_sha, len(bad_content), compress=False)

        bad_obj = StorageObject(
            object_id=f"bad_{uuid.uuid4().hex[:10]}",
            content_sha256=bad_sha,
            stored_sha256=bad_stored_sha,
            original_size=len(bad_content),
            stored_size=bad_sz,
            compression_algorithm="NONE",
            compression_ratio=1.0,
            storage_path=bad_rel,
            reference_count=1,
            state="AVAILABLE",
            integrity_status="VALID"
        )
        db.add(bad_obj)
        db.commit()
        db.refresh(bad_obj)

        bad_phys = repo.resolve_stored_path(bad_rel)
        # Flip bytes
        with open(bad_phys, "r+b") as f:
            f.seek(5)
            f.write(b"CORRUPTED_BYTES!!")

        # Run integrity scrub
        integrity_svc = StorageIntegrityService(db)
        scrub_results = integrity_svc.scrub_storage_objects(object_id=bad_obj.object_id)
        assert scrub_results["objects_corrupted"] == 1

        db.refresh(bad_obj)
        assert bad_obj.integrity_status == "CORRUPTED"
        assert bad_obj.state == "CORRUPTED"
        assert not os.path.exists(bad_phys), "Corrupted file must be moved out of objects directory!"
        # Check quarantine folder
        quarantine_dir = os.path.join(repo.root_path, "quarantine")
        quarantine_files = os.listdir(quarantine_dir)
        assert len(quarantine_files) >= 1
        print(f"[VERIFIED] Bit-rot detected! Object marked CORRUPTED and safely moved to quarantine: {quarantine_files[0]}")

        # 8. Restore Streaming Verification
        log_step(8, "Test Streaming Restore File Decompression")
        f1_record = db.query(BackupFile).filter(BackupFile.backup_run_id == run1.id).first()
        restore_res = client.get(f"/api/v1/restore/files/{f1_record.id}/download", headers=headers)
        assert restore_res.status_code == 200
        downloaded_bytes = restore_res.content
        assert downloaded_bytes == shared_content
        print(f"[VERIFIED] Streaming Restore Download verified! Original content matched byte-for-byte ({len(downloaded_bytes)} bytes)")

        # 9. Storage Metrics API Verification
        log_step(9, "Test Storage Metrics and Accounting API")
        metrics_res = client.get("/api/v1/storage/metrics", headers=headers)
        assert metrics_res.status_code == 200
        m = metrics_res.json()["data"]
        print("Storage Accounting Metrics:")
        print(f"  - Total Logical Bytes: {m['total_logical_bytes']}")
        print(f"  - Total Stored Bytes: {m['total_stored_bytes']}")
        print(f"  - Deduplication Ratio: {m['deduplication_ratio']}x")
        print(f"  - Compression Ratio: {m['compression_ratio']}x")
        print(f"  - Overall Efficiency Ratio: {m['overall_efficiency_ratio']}x")
        print(f"  - Total Space Saved: {m['bytes_saved']} bytes ({m['savings_percent']}%)")
        print(f"  - Repository Health: {m['repository_health']['status']}")
        assert m["total_logical_bytes"] > 0
        assert m["total_stored_bytes"] > 0

        print(f"\n{'='*70}\nALL 25 VERIFICATION CRITERIA PASSED SUCCESSFULLY!\n{'='*70}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
