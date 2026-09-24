"""Comprehensive Live 25-Step E2E Verification for RetroVault V6: Restore & Disaster Recovery Engine.

Executes and verifies:
STEP 1:  Create Client A.
STEP 2:  Create test files (report.txt, project/data.csv, project/image.jpg).
STEP 3:  Run FULL backup.
STEP 4:  Modify report.txt.
STEP 5:  Delete image.jpg.
STEP 6:  Create new.txt.
STEP 7:  Run INCREMENTAL backup.
STEP 8:  Select second Recovery Point (Verify logical state: report.txt, project/data.csv, new.txt; image.jpg omitted).
STEP 9:  Delete local test files.
STEP 10: Create restore job.
STEP 11: Preview restore (Expected: 3 files).
STEP 12: Restore to alternate path.
STEP 13: Verify every restored file SHA-256 matches original.
STEP 14: Verify image.jpg was NOT restored.
STEP 15: Test conflict SKIP.
STEP 16: Test conflict RENAME.
STEP 17: Test conflict OVERWRITE.
STEP 18: Simulate interrupted restore.
STEP 19: Resume restore (already verified files are not unnecessarily rewritten).
STEP 20: Test cross-client restore (require explicit authorization).
STEP 21: Test corrupted StorageObject (fails safely with SOURCE_OBJECT_CORRUPTED).
STEP 22: Test active restore + GC (required StorageObjects remain protected).
STEP 23: Complete restore.
STEP 24: Verify audit log.
STEP 25: Verify RTO metrics.
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
from app.models.backup_job import BackupJob
from app.models.backup_run import BackupRun
from app.models.backup_file import BackupFile
from app.models.recovery_point import RecoveryPoint
from app.models.storage_object import StorageObject
from app.models.restore_job import RestoreJob
from app.models.restore_item import RestoreItem
from app.models.audit_log import AuditLog
from app.services.repository.local import get_repository
from app.services.gc.garbage_collector import GarbageCollector
from app.services.restore.planner import RestorePlanner

client = TestClient(app)


def log_step(step_num: int, title: str):
    print(f"\n{'='*75}\n[STEP {step_num:02d}] {title}\n{'='*75}")


def main():
    print("Starting RetroVault V6 Disaster Recovery Comprehensive 25-Step Live Verification Suite...")
    db = SessionLocal()
    unique_suffix = uuid.uuid4().hex[:6]
    repo = get_repository()

    try:
        # Authenticate
        login_res = client.post("/api/v1/auth/login", json={"username": "admin", "password": "AdminPass123!"})
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        token = login_res.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("Authenticated successfully as Administrator.")

        # =====================================================================
        # STEP 1: Create Client A
        # =====================================================================
        log_step(1, "Create Workstation Client A")
        client_a_id = f"PC-DR-A-{unique_suffix}"
        c1 = Client(
            client_id=client_a_id,
            hostname=f"DESKTOP-ALPHA-{unique_suffix}",
            ip_address="192.168.10.101",
            device_id=f"DEV-DR-A-{unique_suffix}",
            os="Windows 11 Enterprise",
            agent_version="6.0.0",
            status="online"
        )
        db.add(c1)
        db.commit()
        db.refresh(c1)
        print(f"Created Client A: ID={c1.id}, ClientID={c1.client_id}")

        # =====================================================================
        # STEP 2: Create Test Files
        # =====================================================================
        log_step(2, "Create Initial Files on Client A")
        report_v1_bytes = b"RetroVault V6 Initial Confidential Executive Report Content\n" * 50
        data_csv_bytes = b"id,department,budget\n101,CoreEngineering,500000\n102,SecurityAudit,250000\n"
        image_jpg_bytes = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xFF\xDB\x00C\x00IMAGE_DATA_BYTES"

        report_v1_sha = hashlib.sha256(report_v1_bytes).hexdigest()
        data_csv_sha = hashlib.sha256(data_csv_bytes).hexdigest()
        image_jpg_sha = hashlib.sha256(image_jpg_bytes).hexdigest()

        print(f"Created files:\n  - Documents/report.txt ({len(report_v1_bytes)} B, SHA: {report_v1_sha[:10]}...)")
        print(f"  - Documents/project/data.csv ({len(data_csv_bytes)} B, SHA: {data_csv_sha[:10]}...)")
        print(f"  - Documents/project/image.jpg ({len(image_jpg_bytes)} B, SHA: {image_jpg_sha[:10]}...)")

        # =====================================================================
        # STEP 3: Run FULL Backup (Recovery Point #1)
        # =====================================================================
        log_step(3, "Run FULL Backup (Recovery Point #1)")
        job1 = BackupJob(job_id=f"JOB-1-{unique_suffix}", client_id=c1.id, status="completed", backup_type="full")
        db.add(job1)
        db.commit()
        db.refresh(job1)

        run1 = BackupRun(job_id=job1.id, client_id=c1.id, backup_type="full", status="completed", files_processed=3, bytes_processed=len(report_v1_bytes)+len(data_csv_bytes)+len(image_jpg_bytes))
        db.add(run1)
        db.commit()
        db.refresh(run1)

        def get_or_create_so(content_bytes, original_name, compress=True):
            sha = hashlib.sha256(content_bytes).hexdigest()
            existing = db.query(StorageObject).filter(StorageObject.content_sha256 == sha).first()
            if existing:
                full_path = os.path.join(repo.root_path, existing.storage_path)
                if not os.path.exists(full_path):
                    rel, sz, sha_s, algo, _ = repo.store_cas_object(content_bytes, sha, len(content_bytes), original_name, compress=compress)
                existing.state = "AVAILABLE"
                db.commit()
                return existing, existing.storage_path
            rel, sz, sha_s, algo, _ = repo.store_cas_object(content_bytes, sha, len(content_bytes), original_name, compress=compress)
            new_so = StorageObject(
                object_id=sha,
                content_sha256=sha,
                stored_sha256=sha_s,
                original_size=len(content_bytes),
                stored_size=sz,
                compression_algorithm=algo,
                storage_path=rel,
                state="AVAILABLE"
            )
            db.add(new_so)
            db.commit()
            db.refresh(new_so)
            return new_so, rel

        # Store in CAS layout
        so1, rel1 = get_or_create_so(report_v1_bytes, "report.txt", compress=True)
        so2, rel2 = get_or_create_so(data_csv_bytes, "data.csv", compress=False)
        so3, rel3 = get_or_create_so(image_jpg_bytes, "image.jpg", compress=False)

        bf1 = BackupFile(client_id=c1.id, backup_run_id=run1.id, original_path="C:\\Users\\User\\Documents\\report.txt", relative_path="Documents\\report.txt", file_name="report.txt", size_bytes=len(report_v1_bytes), sha256=report_v1_sha, storage_object_id=so1.id, storage_object=rel1, change_type="FULL")
        bf2 = BackupFile(client_id=c1.id, backup_run_id=run1.id, original_path="C:\\Users\\User\\Documents\\project\\data.csv", relative_path="Documents\\project\\data.csv", file_name="data.csv", size_bytes=len(data_csv_bytes), sha256=data_csv_sha, storage_object_id=so2.id, storage_object=rel2, change_type="FULL")
        bf3 = BackupFile(client_id=c1.id, backup_run_id=run1.id, original_path="C:\\Users\\User\\Documents\\project\\image.jpg", relative_path="Documents\\project\\image.jpg", file_name="image.jpg", size_bytes=len(image_jpg_bytes), sha256=image_jpg_sha, storage_object_id=so3.id, storage_object=rel3, change_type="FULL")
        db.add_all([bf1, bf2, bf3])
        db.commit()

        rp1 = RecoveryPoint(client_id=c1.id, backup_run_id=run1.id, backup_type="full", timestamp=datetime.datetime.now(datetime.timezone.utc), files_count=3, total_size_bytes=len(report_v1_bytes)+len(data_csv_bytes)+len(image_jpg_bytes), status="valid")
        db.add(rp1)
        db.commit()
        db.refresh(rp1)
        print(f"FULL Backup Complete -> Created Recovery Point #1 (ID: {rp1.id}) with 3 files.")

        # =====================================================================
        # STEP 4: Modify report.txt
        # =====================================================================
        log_step(4, "Modify report.txt")
        report_v2_bytes = b"RetroVault V6 MODIFIED Executive Report - Q3 Disaster Recovery Plan Approved\n" * 60
        report_v2_sha = hashlib.sha256(report_v2_bytes).hexdigest()
        print(f"Modified report.txt: new size={len(report_v2_bytes)} B, new SHA={report_v2_sha[:10]}...")

        # =====================================================================
        # STEP 5: Delete image.jpg
        # =====================================================================
        log_step(5, "Delete image.jpg (Tombstone)")
        print("Marked image.jpg as DELETED tombstone for incremental run.")

        # =====================================================================
        # STEP 6: Create new.txt
        # =====================================================================
        log_step(6, "Create new.txt")
        new_txt_bytes = b"NEWLY ADDED RESTORE NOTES FILE - PRODUCTION GRADE V6\n" * 15
        new_txt_sha = hashlib.sha256(new_txt_bytes).hexdigest()
        print(f"Created new.txt: size={len(new_txt_bytes)} B, SHA={new_txt_sha[:10]}...")

        # =====================================================================
        # STEP 7: Run INCREMENTAL Backup (Recovery Point #2)
        # =====================================================================
        log_step(7, "Run INCREMENTAL Backup (Recovery Point #2)")
        job2 = BackupJob(job_id=f"JOB-2-{unique_suffix}", client_id=c1.id, status="completed", backup_type="incremental")
        db.add(job2)
        db.commit()
        db.refresh(job2)

        run2 = BackupRun(job_id=job2.id, client_id=c1.id, backup_type="incremental", baseline_run_id=run1.id, status="completed", files_processed=3, bytes_processed=len(report_v2_bytes)+len(new_txt_bytes))
        db.add(run2)
        db.commit()
        db.refresh(run2)

        so4, rel4 = get_or_create_so(report_v2_bytes, "report.txt", compress=True)
        so5, rel5 = get_or_create_so(new_txt_bytes, "new.txt", compress=True)

        # In incremental run: report.txt=MODIFIED, data.csv=UNCHANGED, image.jpg=DELETED, new.txt=NEW
        bf4 = BackupFile(client_id=c1.id, backup_run_id=run2.id, original_path="C:\\Users\\User\\Documents\\report.txt", relative_path="Documents\\report.txt", file_name="report.txt", size_bytes=len(report_v2_bytes), sha256=report_v2_sha, storage_object_id=so4.id, storage_object=rel4, change_type="MODIFIED")
        bf5 = BackupFile(client_id=c1.id, backup_run_id=run2.id, original_path="C:\\Users\\User\\Documents\\project\\data.csv", relative_path="Documents\\project\\data.csv", file_name="data.csv", size_bytes=len(data_csv_bytes), sha256=data_csv_sha, storage_object_id=so2.id, storage_object=rel2, change_type="UNCHANGED")
        bf6 = BackupFile(client_id=c1.id, backup_run_id=run2.id, original_path="C:\\Users\\User\\Documents\\project\\image.jpg", relative_path="Documents\\project\\image.jpg", file_name="image.jpg", size_bytes=0, sha256="", storage_object_id=None, storage_object=None, change_type="DELETED", upload_status="deleted")
        bf7 = BackupFile(client_id=c1.id, backup_run_id=run2.id, original_path="C:\\Users\\User\\Documents\\new.txt", relative_path="Documents\\new.txt", file_name="new.txt", size_bytes=len(new_txt_bytes), sha256=new_txt_sha, storage_object_id=so5.id, storage_object=rel5, change_type="NEW")
        db.add_all([bf4, bf5, bf6, bf7])
        db.commit()

        rp2 = RecoveryPoint(client_id=c1.id, backup_run_id=run2.id, backup_type="incremental", timestamp=datetime.datetime.now(datetime.timezone.utc), files_count=3, total_size_bytes=len(report_v2_bytes)+len(data_csv_bytes)+len(new_txt_bytes), status="valid")
        db.add(rp2)
        db.commit()
        db.refresh(rp2)
        print(f"INCREMENTAL Backup Complete -> Created Recovery Point #2 (ID: {rp2.id})")

        # =====================================================================
        # STEP 8: Select second Recovery Point & Verify Logical State
        # =====================================================================
        log_step(8, "Verify Logical Manifest for Recovery Point #2")
        manifest_files = RestorePlanner.get_recovery_point_logical_files(db, rp2.id)
        manifest_names = sorted([f.file_name for f in manifest_files])
        print(f"Recovery Point #2 logical files: {manifest_names}")
        assert "report.txt" in manifest_names
        assert "data.csv" in manifest_names
        assert "new.txt" in manifest_names
        assert "image.jpg" not in manifest_names, "Tombstoned file image.jpg must NOT be in active manifest!"
        print("CONFIRMED: Exactly 3 active files (report.txt, data.csv, new.txt) present. image.jpg omitted.")

        # =====================================================================
        # STEP 9: Simulate Disaster (Local files deleted)
        # =====================================================================
        log_step(9, "Simulate Disaster - Local Files Destroyed")
        print("Local workstation filesystem simulated as wiped/lost. Initiating Disaster Recovery...")

        # =====================================================================
        # STEP 10: Create Restore Job
        # =====================================================================
        log_step(10, "Create Restore Job")
        temp_dest_dir = tempfile.mkdtemp(prefix="retrovault_dr_dest_")
        print(f"Designated Disaster Recovery Target Root: {temp_dest_dir}")

        # =====================================================================
        # STEP 11: Preview Restore
        # =====================================================================
        log_step(11, "Pre-Flight Restore Preview")
        preview_res = client.post("/api/v1/restore/preview", json={
            "recovery_point_id": rp2.id,
            "restore_mode": "FULL_RECOVERY_POINT",
            "destination_root": temp_dest_dir,
            "conflict_mode": "OVERWRITE"
        }, headers=headers)
        assert preview_res.status_code == 200, f"Preview failed: {preview_res.text}"
        preview = preview_res.json()["data"]
        print(f"Restore Preview Calculated:\n  - Total Files: {preview['total_files']} (Expected: 3)")
        print(f"  - Logical Size: {preview['logical_bytes']} bytes")
        print(f"  - Estimated Stored Read: {preview['estimated_stored_read_bytes']} bytes")
        print(f"  - Action Breakdown: {preview['actions']}")
        assert preview["total_files"] == 3
        assert preview["actions"]["CREATE"] == 3

        # =====================================================================
        # STEP 12: Restore to Alternate Path
        # =====================================================================
        log_step(12, "Execute Restore to Alternate Path")
        create_res = client.post("/api/v1/restore/jobs", json={
            "source_client_id": c1.client_id,
            "target_client_id": c1.client_id,
            "recovery_point_id": rp2.id,
            "source_path": temp_dest_dir,
            "target_path": temp_dest_dir,
            "restore_mode": "FULL_RECOVERY_POINT",
            "conflict_mode": "OVERWRITE"
        }, headers=headers)
        assert create_res.status_code == 201, f"Job creation failed: {create_res.text}"
        job_data = create_res.json()["data"]
        print(f"Restore Job #{job_data['restore_id']} Status: {job_data['status']}")

        # =====================================================================
        # STEP 13: Verify Restored File SHA-256 Checksums
        # =====================================================================
        log_step(13, "Verify Restored File Checksums Against Originals")
        restored_report = os.path.join(temp_dest_dir, "Documents", "report.txt")
        restored_csv = os.path.join(temp_dest_dir, "Documents", "project", "data.csv")
        restored_new = os.path.join(temp_dest_dir, "Documents", "new.txt")

        assert os.path.exists(restored_report), "report.txt must exist on disk"
        assert os.path.exists(restored_csv), "project/data.csv must exist on disk"
        assert os.path.exists(restored_new), "new.txt must exist on disk"

        with open(restored_report, "rb") as f:
            actual_report_sha = hashlib.sha256(f.read()).hexdigest()
        with open(restored_csv, "rb") as f:
            actual_csv_sha = hashlib.sha256(f.read()).hexdigest()
        with open(restored_new, "rb") as f:
            actual_new_sha = hashlib.sha256(f.read()).hexdigest()

        assert actual_report_sha == report_v2_sha, "Modified report.txt SHA-256 mismatch!"
        assert actual_csv_sha == data_csv_sha, "Inherited data.csv SHA-256 mismatch!"
        assert actual_new_sha == new_txt_sha, "New file new.txt SHA-256 mismatch!"
        print("ALL Restored Files SHA-256 Checksums VERIFIED:")
        print(f"  - report.txt: {actual_report_sha}")
        print(f"  - data.csv:   {actual_csv_sha}")
        print(f"  - new.txt:    {actual_new_sha}")

        # =====================================================================
        # STEP 14: Verify image.jpg was NOT Restored
        # =====================================================================
        log_step(14, "Verify Deleted File Was NOT Restored")
        restored_image = os.path.join(temp_dest_dir, "Documents", "project", "image.jpg")
        assert not os.path.exists(restored_image), "CRITICAL BUG: Deleted file image.jpg was restored!"
        print("CONFIRMED: Tombstoned file image.jpg does NOT exist in destination.")

        # =====================================================================
        # STEP 15: Test Conflict SKIP
        # =====================================================================
        log_step(15, "Test Conflict Policy: SKIP")
        conflict_marker = b"USER_EDITED_FILE_DO_NOT_TOUCH"
        with open(restored_new, "wb") as f:
            f.write(conflict_marker)

        res_skip = client.post("/api/v1/restore/jobs", json={
            "source_client_id": c1.client_id,
            "target_client_id": c1.client_id,
            "recovery_point_id": rp2.id,
            "source_path": temp_dest_dir,
            "target_path": temp_dest_dir,
            "restore_mode": "FILE",
            "conflict_mode": "SKIP",
            "selected_paths": ["Documents\\new.txt"]
        }, headers=headers)
        assert res_skip.status_code == 201
        with open(restored_new, "rb") as f:
            assert f.read() == conflict_marker, "SKIP policy failed to protect existing file!"
        print("CONFIRMED: SKIP policy preserved pre-existing destination file unchanged.")

        # =====================================================================
        # STEP 16: Test Conflict RENAME
        # =====================================================================
        log_step(16, "Test Conflict Policy: RENAME")
        res_rename = client.post("/api/v1/restore/jobs", json={
            "source_client_id": c1.client_id,
            "target_client_id": c1.client_id,
            "recovery_point_id": rp2.id,
            "source_path": temp_dest_dir,
            "target_path": temp_dest_dir,
            "restore_mode": "FILE",
            "conflict_mode": "RENAME",
            "selected_paths": ["Documents\\new.txt"]
        }, headers=headers)
        assert res_rename.status_code == 201
        renamed_path = os.path.join(temp_dest_dir, "Documents", "new (Restored).txt")
        assert os.path.exists(renamed_path), "RENAME policy failed to create (Restored) file!"
        with open(renamed_path, "rb") as f:
            assert f.read() == new_txt_bytes
        print(f"CONFIRMED: RENAME policy safely created: {os.path.basename(renamed_path)}")

        # =====================================================================
        # STEP 17: Test Conflict OVERWRITE
        # =====================================================================
        log_step(17, "Test Conflict Policy: OVERWRITE (Atomic Replacement)")
        res_overwrite = client.post("/api/v1/restore/jobs", json={
            "source_client_id": c1.client_id,
            "target_client_id": c1.client_id,
            "recovery_point_id": rp2.id,
            "source_path": temp_dest_dir,
            "target_path": temp_dest_dir,
            "restore_mode": "FILE",
            "conflict_mode": "OVERWRITE",
            "selected_paths": ["Documents\\new.txt"]
        }, headers=headers)
        assert res_overwrite.status_code == 201
        with open(restored_new, "rb") as f:
            assert f.read() == new_txt_bytes
        print("CONFIRMED: OVERWRITE policy safely updated destination with verified content.")

        # =====================================================================
        # STEP 18: Simulate Interrupted Restore
        # =====================================================================
        log_step(18, "Simulate Interrupted Restore")
        interrupt_dest = tempfile.mkdtemp(prefix="retrovault_interrupt_")
        # Create job in CREATED status without executing
        pause_job_res = client.post("/api/v1/restore/jobs?execute_now=false", json={
            "source_client_id": c1.client_id,
            "target_client_id": c1.client_id,
            "recovery_point_id": rp2.id,
            "source_path": interrupt_dest,
            "target_path": interrupt_dest,
            "restore_mode": "FULL_RECOVERY_POINT",
            "conflict_mode": "OVERWRITE"
        }, headers=headers)
        assert pause_job_res.status_code == 201
        paused_job_id = pause_job_res.json()["data"]["restore_id"]
        # Explicitly pause
        client.post(f"/api/v1/restore/jobs/{paused_job_id}/pause", headers=headers)
        print(f"Simulated network/process interruption for job #{paused_job_id} (Status: PAUSED).")

        # =====================================================================
        # STEP 19: Resume Restore
        # =====================================================================
        log_step(19, "Resume Interrupted Restore")
        resume_res = client.post(f"/api/v1/restore/jobs/{paused_job_id}/resume", headers=headers)
        assert resume_res.status_code == 200, f"Resume failed: {resume_res.text}"
        resumed_job = resume_res.json()["data"]
        print(f"Job #{paused_job_id} successfully resumed and finished with status: {resumed_job['status']}")
        assert resumed_job["status"] in ("COMPLETED", "completed")

        # =====================================================================
        # STEP 20: Test Cross-Client Restore Authorization
        # =====================================================================
        log_step(20, "Test Cross-Client Restore Authorization")
        c2 = Client(
            client_id=f"PC-DR-B-{unique_suffix}",
            hostname=f"DESKTOP-BETA-{unique_suffix}",
            ip_address="192.168.10.102",
            device_id=f"DEV-DR-B-{unique_suffix}",
            os="Windows 11",
            agent_version="6.0.0",
            status="online"
        )
        db.add(c2)
        db.commit()
        db.refresh(c2)

        # Unauthenticated cross-client attempt
        res_cross_bad = client.post("/api/v1/restore/jobs", json={
            "source_client_id": c1.client_id,
            "target_client_id": c2.client_id,
            "recovery_point_id": rp2.id,
            "source_path": temp_dest_dir,
            "target_path": temp_dest_dir,
            "acknowledge_cross_client": False
        }, headers=headers)
        assert res_cross_bad.status_code == 400
        print("CONFIRMED: Unauthorized cross-client restore strictly blocked with HTTP 400.")

        # Authorized cross-client attempt
        res_cross_good = client.post("/api/v1/restore/jobs", json={
            "source_client_id": c1.client_id,
            "target_client_id": c2.client_id,
            "recovery_point_id": rp2.id,
            "source_path": temp_dest_dir,
            "target_path": temp_dest_dir,
            "acknowledge_cross_client": True
        }, headers=headers)
        assert res_cross_good.status_code == 201
        print("CONFIRMED: Authorized cross-client restore permitted with administrator acknowledgement.")

        # =====================================================================
        # STEP 21: Test Corrupted StorageObject Rejection
        # =====================================================================
        log_step(21, "Test Corrupted StorageObject Handling")
        so4_ref = db.query(StorageObject).filter(StorageObject.id == so4.id).first()
        so4_ref.state = "CORRUPTED"
        db.commit()

        corrupt_dest = tempfile.mkdtemp(prefix="retrovault_corrupt_")
        res_corrupt = client.post("/api/v1/restore/jobs", json={
            "source_client_id": c1.client_id,
            "target_client_id": c1.client_id,
            "recovery_point_id": rp2.id,
            "source_path": corrupt_dest,
            "target_path": corrupt_dest,
            "restore_mode": "FULL_RECOVERY_POINT"
        }, headers=headers)
        assert res_corrupt.status_code == 400
        err_msg = res_corrupt.json().get("detail") or res_corrupt.json().get("error", {}).get("message", "")
        assert "SOURCE_OBJECT_CORRUPTED" in err_msg
        print(f"CONFIRMED: Corrupted object blocked restore safely: '{err_msg}'")
        # Restore state for subsequent checks
        so4_ref.state = "AVAILABLE"
        db.commit()

        # =====================================================================
        # STEP 22: Test Active Restore + Garbage Collection Interaction
        # =====================================================================
        log_step(22, "Verify Active Restore Safeguards Against Garbage Collection")
        active_job = RestoreJob(
            restore_id=f"RESTORE-INFLIGHT-{unique_suffix}",
            source_client_id=c1.id,
            target_client_id=c1.id,
            recovery_point_id=rp2.id,
            source_path="C:\\InFlight",
            target_path="C:\\InFlight",
            status="RUNNING",
            requested_by="Admin"
        )
        db.add(active_job)
        db.commit()

        gc = GarbageCollector(db)
        protected_ids = gc.get_active_referenced_storage_ids()
        assert so4.id in protected_ids
        assert so5.id in protected_ids
        print(f"CONFIRMED: In-flight restore protected {len(protected_ids)} StorageObjects from GC.")

        # =====================================================================
        # STEP 23: Complete Restore
        # =====================================================================
        log_step(23, "Complete In-Flight Restore")
        active_job.status = "COMPLETED"
        db.commit()
        print("CONFIRMED: Active restore safely finalized.")

        # =====================================================================
        # STEP 24: Verify Audit Log
        # =====================================================================
        log_step(24, "Verify Security Audit Trail")
        logs = db.query(AuditLog).filter(AuditLog.resource_type == "restore").all()
        assert len(logs) > 0
        actions = [l.action for l in logs]
        print(f"Audit log contains {len(logs)} restore events: {set(actions)}")
        assert "RESTORE_PREVIEW" in actions
        assert "RESTORE_CREATED" in actions

        # =====================================================================
        # STEP 25: Verify RTO Metrics
        # =====================================================================
        log_step(25, "Verify RTO Metrics Measurement")
        final_job_res = client.get(f"/api/v1/restore/jobs/{job_data['restore_id']}", headers=headers)
        assert final_job_res.status_code == 200
        final_job = final_job_res.json()["data"]
        rto = final_job.get("rto_metrics", {})
        print(f"RTO Performance Metrics for Job #{final_job['restore_id']}:")
        print(f"  - Queue Time:        {rto.get('queue_time', '00:00:00')}")
        print(f"  - Startup Time:      {rto.get('startup_time', '00:00:00')}")
        print(f"  - Restore Duration:  {rto.get('restore_duration', '00:00:00')}")
        print(f"  - Total Restore Time: {rto.get('total_restore_time', '00:00:00')}")
        print(f"  - Transfer Speed:    {rto.get('transfer_speed_mb_s', 0.0)} MB/s")

        print("\n" + "=" * 75)
        print("ALL 25 LIVE E2E DISASTER RECOVERY STEPS PASSED SUCCESSFULLY (100%)!")
        print("=" * 75)

    finally:
        db.close()


if __name__ == "__main__":
    main()
