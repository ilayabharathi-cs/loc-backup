"""Automated Non-Destructive Disaster Recovery Verification Service for RetroVault V7."""

import os
import shutil
import time
import uuid
import hashlib
import tempfile
import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.recovery_point import RecoveryPoint
from app.models.security_models import DrTest
from app.services.restore.planner import RestorePlanner
from app.services.repository.local import get_repository


class DrTester:
    """Performs isolated, sandbox restore drills with checksum verification without modifying target disks."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = get_repository()

    def run_dr_drill(self, recovery_point_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Executes an end-to-end non-destructive disaster recovery verification test.
        """
        if recovery_point_id:
            rp = self.db.query(RecoveryPoint).filter(RecoveryPoint.id == recovery_point_id).first()
        else:
            rp = self.db.query(RecoveryPoint).filter(
                RecoveryPoint.status.in_(["valid", "completed"])
            ).order_by(RecoveryPoint.created_at.desc()).first()

        if not rp:
            raise ValueError("No valid Recovery Point available to test")

        test_id = f"DR-TEST-{uuid.uuid4().hex[:8].upper()}"
        sandbox_dir = tempfile.mkdtemp(prefix=f"retrovault_dr_sandbox_{test_id}_")

        start_time = time.perf_counter()
        now = datetime.datetime.now(datetime.timezone.utc)
        files_tested = 0
        bytes_tested = 0
        files_verified = 0
        failures = 0
        error_msg = None

        try:
            # 1. Retrieve logical point-in-time manifest
            logical_files = RestorePlanner.get_recovery_point_logical_files(self.db, rp.id)
            files_tested = len(logical_files)

            # 2. Restore and verify in sandbox
            for bf in logical_files:
                if bf.change_type == "DELETED" or not bf.storage_object:
                    continue

                bytes_tested += (bf.size_bytes or 0)
                rel_path = bf.relative_path or bf.file_name
                dest_path = os.path.join(sandbox_dir, rel_path)
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)

                # Read from CAS repository (transparent decompression)
                file_bytes = self.repo.read_cas_object(bf.storage_object)

                with open(dest_path, "wb") as f:
                    f.write(file_bytes)

                # Verify checksum against manifest
                actual_sha = hashlib.sha256(file_bytes).hexdigest()
                if actual_sha == bf.sha256:
                    files_verified += 1
                else:
                    failures += 1
                    error_msg = f"Checksum mismatch on {rel_path}: expected {bf.sha256}, got {actual_sha}"

        except Exception as e:
            failures += 1
            error_msg = str(e)

        duration = round(time.perf_counter() - start_time, 4)

        # 3. Clean up sandbox destination completely
        try:
            if os.path.exists(sandbox_dir):
                shutil.rmtree(sandbox_dir, ignore_errors=True)
        except Exception:
            pass

        # 4. Record result in database
        result_status = "PASSED" if (failures == 0 and files_tested > 0) else "FAILED"
        if failures > 0 and files_verified > 0:
            result_status = "PARTIAL"

        dr_record = DrTest(
            test_id=test_id,
            recovery_point_id=rp.id,
            target_path=sandbox_dir,
            files_tested=files_tested,
            bytes_tested=bytes_tested,
            files_verified=files_verified,
            failures=failures,
            duration_seconds=duration,
            result=result_status,
            error_message=error_msg,
            started_at=now,
            completed_at=datetime.datetime.now(datetime.timezone.utc)
        )
        self.db.add(dr_record)
        self.db.commit()
        self.db.refresh(dr_record)

        return {
            "test_id": test_id,
            "recovery_point_id": rp.id,
            "result": result_status,
            "files_tested": files_tested,
            "bytes_tested": bytes_tested,
            "files_verified": files_verified,
            "failures": failures,
            "duration_seconds": duration,
            "error_message": error_msg,
            "cleaned_up": not os.path.exists(sandbox_dir),
            "started_at": dr_record.started_at.isoformat(),
            "completed_at": dr_record.completed_at.isoformat() if dr_record.completed_at else None
        }
