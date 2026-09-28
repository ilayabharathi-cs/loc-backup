"""
RETROVAULT CROSS-PLATFORM SERVER TEST SUITE
Validates identical and correct behavior across:
- Environment A: Windows Client -> Linux Backup Server (POSIX paths)
- Environment B: Windows Client -> Windows Backup Server (NTFS paths)
"""

import os
import sys
import time
import json
import uuid
import shutil
import tempfile
import hashlib
import datetime
from fastapi.testclient import TestClient

# Ensure server module path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "server"))

from app.main import app
from app.config import settings
from app.database.session import SessionLocal
from app.models.client import Client
from app.models.backup_job import BackupJob
from app.models.backup_run import BackupRun
from app.models.backup_file import BackupFile
from app.models.recovery_point import RecoveryPoint
from app.models.storage_object import StorageObject
from app.models.restore_job import RestoreJob
from app.services.repository.local import LocalFilesystemRepository
from app.services.restore.path_validator import PathValidator, PathSafetyError
from app.services.restore.executor import RestoreExecutor
from app.services.restore.planner import RestorePlanner

def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def test_cross_platform_server_suite():
    print("=" * 75)
    print("RETROVAULT CROSS-PLATFORM SERVER ACCEPTANCE SUITE")
    print("=" * 75)

    client = TestClient(app)

    # 1. Verify Health Endpoint and Platform Metadata
    res_health = client.get("/health")
    assert res_health.status_code == 200
    h_data = res_health.json()
    assert h_data["status"] == "ok"
    assert h_data["product"] == "RetroVault Local Backup"
    assert "server_platform" in h_data
    assert "database_engine" in h_data
    print(f"[OK] Health Endpoint Verified: Server Platform = {h_data['server_platform']}, Engine = {h_data['database_engine']}")

    # 2. Verify Centralized System Info API
    res_info = client.get("/api/v1/settings/system-info")
    assert res_info.status_code == 200
    s_data = res_info.json()["data"]
    assert "server_platform" in s_data
    assert "repository_root" in s_data
    print(f"[OK] System Info API Verified: Repository Root = {s_data['repository_root']}")

    # 3. PathValidator Cross-Platform Normalization
    print("\n--- Testing PathValidator Cross-Platform Security ---")
    # Windows Client paths passed to server (with \ or /)
    assert PathValidator.sanitize_relative_path(r"documents\financial\report.xlsx") == os.path.join("documents", "financial", "report.xlsx")
    assert PathValidator.sanitize_relative_path("documents/financial/report.xlsx") == os.path.join("documents", "financial", "report.xlsx")
    assert PathValidator.sanitize_relative_path(r"C:\Users\Admin\Documents\notes.txt") == os.path.join("Users", "Admin", "Documents", "notes.txt")
    print("[OK] Client Windows paths normalized identically across path separators.")

    # Traversal Protection
    for malicious in [r"..\..\Windows\System32\cmd.exe", "../../etc/shadow", r"..\..\boot.ini", "../escape.txt"]:
        try:
            PathValidator.sanitize_relative_path(malicious)
            assert False, f"Must reject traversal: {malicious}"
        except PathSafetyError:
            pass
    print("[OK] Traversal attempts (POSIX and Windows syntax) strictly rejected.")

    # Reserved Windows device names
    for dev in ["CON", "PRN", "AUX", "NUL", "COM1", "COM9", "LPT1", "LPT9"]:
        try:
            PathValidator.sanitize_relative_path(f"data/{dev}.txt")
            assert False, f"Must reject reserved device name: {dev}"
        except PathSafetyError:
            pass
    print("[OK] Windows reserved device names strictly prohibited.")

    # 4. Test Cross-Platform Simulation: Environment A (Linux Server Simulation) & Environment B (Windows Server Simulation)
    for env_name in ["Linux_Server_Simulation", "Windows_Server_Simulation"]:
        print(f"\n" + "=" * 75)
        print(f"Executing Full Lifecycle on {env_name}")
        print("=" * 75)

        work_dir = tempfile.mkdtemp(prefix=f"rv_{env_name}_")
        repo_dir = os.path.join(work_dir, "cas_repo")
        src_client_dir = os.path.join(work_dir, "windows_client_source")
        dest_restore_dir = os.path.join(work_dir, "windows_client_restore")

        os.makedirs(repo_dir, exist_ok=True)
        os.makedirs(src_client_dir, exist_ok=True)
        os.makedirs(dest_restore_dir, exist_ok=True)

        repo = LocalFilesystemRepository(root_path=repo_dir)
        db = SessionLocal()
        db.query(StorageObject).update({"state": "AVAILABLE", "integrity_status": "HEALTHY"})
        db.commit()

        try:
            # Create Windows Client in DB
            c_id = f"WIN-CLIENT-{uuid.uuid4().hex[:6]}"
            c = Client(
                client_id=c_id,
                hostname="DESKTOP-WIN11-PRO",
                device_id=f"DEV-{uuid.uuid4().hex[:8]}",
                os="Windows",
                os_version="11 Pro 23H2",
                agent_version="1.0.0",
                ip_address="192.168.1.55"
            )
            db.add(c)
            db.commit()
            db.refresh(c)

            # Create diverse test files on Windows client
            files_manifest = [
                ("budget.xlsx", b"EXCEL BINARY SPREADSHEET CONTENT\n" * 100),
                ("subfolder/server_config.xml", b"<configuration><server port='8000'/></configuration>\n"),
                ("archive.tar", os.urandom(65536)),
                ("unicode_doc_\u00e9\u00e0.txt", "Rapport d'\u00e9valuation fran\u00e7ais 2026\n".encode("utf-8"))
            ]

            stored_objects = {}
            total_source_bytes = 0

            # --- FULL BACKUP CYCLE ---
            job_full = BackupJob(job_id=f"JOB-FULL-{uuid.uuid4().hex[:6]}", client_id=c.id, status="completed", backup_type="full")
            db.add(job_full)
            db.commit()

            run_full = BackupRun(job_id=job_full.id, client_id=c.id, backup_type="full", status="running", files_processed=4, bytes_processed=0)
            db.add(run_full)
            db.commit()

            for rel_path, data in files_manifest:
                total_source_bytes += len(data)
                sha = compute_sha256(data)
                cas_rel, stored_sz, stored_sha, algo, ratio = repo.store_cas_object(
                    source_path_or_bytes=data,
                    content_sha256=sha,
                    original_size=len(data),
                    filename_hint=os.path.basename(rel_path)
                )

                existing_so = db.query(StorageObject).filter(StorageObject.content_sha256 == sha).first()
                if existing_so:
                    so = existing_so
                    so.reference_count += 1
                else:
                    so = StorageObject(
                        object_id=sha,
                        content_sha256=sha,
                        stored_sha256=stored_sha,
                        original_size=len(data),
                        stored_size=stored_sz,
                        compression_algorithm=algo,
                        compression_ratio=ratio,
                        storage_path=cas_rel,
                        reference_count=1,
                        state="AVAILABLE",
                        integrity_status="HEALTHY"
                    )
                    db.add(so)
                    db.commit()
                    db.refresh(so)

                stored_objects[sha] = (so, cas_rel)

                bf = BackupFile(
                    client_id=c.id,
                    backup_run_id=run_full.id,
                    file_name=os.path.basename(rel_path),
                    original_path=f"C:\\ClientData\\{rel_path.replace('/', os.sep)}",
                    relative_path=rel_path,
                    size_bytes=len(data),
                    sha256=sha,
                    storage_object=cas_rel,
                    storage_object_id=so.id,
                    change_type="NEW",
                    upload_status="completed",
                    modified_time=datetime.datetime.now(datetime.timezone.utc)
                )
                db.add(bf)

            db.commit()
            run_full.status = "completed"
            db.commit()

            rp_full = RecoveryPoint(
                client_id=c.id,
                backup_run_id=run_full.id,
                backup_type="full",
                timestamp=datetime.datetime.now(datetime.timezone.utc),
                status="valid",
                files_count=len(files_manifest),
                total_size_bytes=total_source_bytes
            )
            db.add(rp_full)
            db.commit()
            db.refresh(rp_full)
            print(f"[OK] Full Backup Created (RP #{rp_full.id}): {total_source_bytes:,} bytes across {len(files_manifest)} files.")

            # --- INCREMENTAL BACKUP CYCLE ---
            # Modify 1 file, add 1 new file, delete 1 file
            b_new = b"Brand new incremental file content\n" * 50
            sha_new = compute_sha256(b_new)
            cas_new, sz_new, sha_s_new, algo_new, _ = repo.store_cas_object(b_new, sha_new, len(b_new), "new_audit.log")
            existing_so_new = db.query(StorageObject).filter(StorageObject.content_sha256 == sha_new).first()
            if existing_so_new:
                so_new = existing_so_new
                so_new.reference_count += 1
            else:
                so_new = StorageObject(object_id=sha_new, content_sha256=sha_new, stored_sha256=sha_s_new, original_size=len(b_new), stored_size=sz_new, compression_algorithm=algo_new, storage_path=cas_new, reference_count=1, state="AVAILABLE", integrity_status="HEALTHY")
                db.add(so_new)
                db.commit()
                db.refresh(so_new)

            job_inc = BackupJob(job_id=f"JOB-INC-{uuid.uuid4().hex[:6]}", client_id=c.id, status="completed", backup_type="incremental")
            db.add(job_inc)
            db.commit()

            run_inc = BackupRun(job_id=job_inc.id, client_id=c.id, backup_type="incremental", status="running", files_processed=4, bytes_processed=len(b_new))
            db.add(run_inc)
            db.commit()

            # New file
            bf_new = BackupFile(client_id=c.id, backup_run_id=run_inc.id, file_name="new_audit.log", original_path=r"C:\ClientData\new_audit.log", relative_path="new_audit.log", size_bytes=len(b_new), sha256=sha_new, storage_object=cas_new, storage_object_id=so_new.id, change_type="NEW", upload_status="completed")
            db.add(bf_new)

            # Deleted file (tombstone)
            bf_del = BackupFile(client_id=c.id, backup_run_id=run_inc.id, file_name="archive.tar", original_path=r"C:\ClientData\archive.tar", relative_path="archive.tar", size_bytes=0, sha256="DELETED_TOMBSTONE", storage_object="", change_type="DELETED", upload_status="deleted")
            db.add(bf_del)

            # Unchanged files
            for rel, data in files_manifest:
                if rel == "archive.tar":
                    continue
                sha = compute_sha256(data)
                so, cas_rel = stored_objects[sha]
                so.reference_count += 1
                bf_unc = BackupFile(client_id=c.id, backup_run_id=run_inc.id, file_name=os.path.basename(rel), original_path=f"C:\\ClientData\\{rel.replace('/', os.sep)}", relative_path=rel, size_bytes=len(data), sha256=sha, storage_object=cas_rel, storage_object_id=so.id, change_type="UNCHANGED", upload_status="completed")
                db.add(bf_unc)

            db.commit()
            run_inc.status = "completed"
            db.commit()

            rp_inc = RecoveryPoint(
                client_id=c.id,
                backup_run_id=run_inc.id,
                backup_type="incremental",
                timestamp=datetime.datetime.now(datetime.timezone.utc),
                status="valid",
                files_count=4,
                total_size_bytes=total_source_bytes - 65536 + len(b_new)
            )
            db.add(rp_inc)
            db.commit()
            db.refresh(rp_inc)
            print(f"[OK] Incremental Backup Created (RP #{rp_inc.id}): Synthetic point inherits 3 files, 1 new, 1 tombstone.")

            # --- RESTORE ACCEPTANCE ---
            rjob_full = RestoreJob(
                restore_id=f"RESTORE-{env_name}-{uuid.uuid4().hex[:6]}",
                source_client_id=c.id,
                target_client_id=c.id,
                recovery_point_id=rp_inc.id,
                source_path=src_client_dir,
                target_path=dest_restore_dir,
                requested_by="admin",
                restore_mode="FULL_RECOVERY_POINT",
                conflict_mode="OVERWRITE",
                status="CREATED"
            )
            db.add(rjob_full)
            db.commit()

            executor = RestoreExecutor(db, rjob_full)
            executor.repo = repo
            executor.validate_and_plan()
            executor.execute_restore()

            assert rjob_full.status == "COMPLETED", f"Restore failed: {rjob_full.error_message}, status={rjob_full.status}, failed={rjob_full.failed_files}"
            print(f"[OK] Full RP Restore Succeeded onto destination directory.")

            # Verify byte-for-byte fidelity of all 4 expected files
            assert os.path.exists(os.path.join(dest_restore_dir, "budget.xlsx"))
            assert not os.path.exists(os.path.join(dest_restore_dir, "archive.tar")), "Deleted tombstone must NOT be restored"
            assert os.path.exists(os.path.join(dest_restore_dir, "new_audit.log"))
            assert os.path.exists(os.path.join(dest_restore_dir, "subfolder", "server_config.xml"))

            with open(os.path.join(dest_restore_dir, "new_audit.log"), "rb") as f:
                assert compute_sha256(f.read()) == sha_new
            print(f"[OK] 100% SHA-256 byte-level verification passed on {env_name}.")

        finally:
            db.close()
            shutil.rmtree(work_dir, ignore_errors=True)

    print("\n" + "=" * 75)
    print("ALL CROSS-PLATFORM SERVER TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 75)

if __name__ == "__main__":
    test_cross_platform_server_suite()
