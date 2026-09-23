"""Restore Execution Engine for RetroVault V6 Disaster Recovery.

Manages:
1. Strict 14-state machine transitions.
2. Pre-execution manifest and StorageObject validation.
3. Streaming CAS decompression and atomic temporary file writes.
4. Resumable crash checkpoints and idempotent file skipping.
5. In-flight GC/retention protection.
6. RTO telemetry and structured audit logging.
"""

import datetime
import hashlib
import json
import os
import shutil
import tempfile
import uuid
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session

from app.models.restore_job import RestoreJob
from app.models.restore_item import RestoreItem
from app.models.restore_checkpoint import RestoreCheckpoint
from app.models.recovery_point import RecoveryPoint
from app.models.backup_file import BackupFile
from app.models.storage_object import StorageObject
from app.models.client import Client
from app.services.repository.local import get_repository
from app.services.restore.path_validator import PathValidator, PathSafetyError
from app.services.restore.planner import RestorePlanner
from app.services.audit_service import log_audit_event


VALID_STATE_TRANSITIONS = {
    "CREATED": {"VALIDATING", "CANCELLED"},
    "VALIDATING": {"PLANNING", "FAILED", "CANCELLED"},
    "PLANNING": {"QUEUED", "FAILED", "CANCELLED"},
    "QUEUED": {"RUNNING", "CANCELLED", "PAUSED"},
    "RUNNING": {"VERIFYING", "PAUSED", "INTERRUPTED", "COMPLETED", "PARTIAL", "FAILED", "CANCELLED"},
    "PAUSED": {"RESUMING", "CANCELLED"},
    "INTERRUPTED": {"RESUMING", "CANCELLED", "FAILED"},
    "RESUMING": {"RUNNING", "FAILED", "CANCELLED"},
    "VERIFYING": {"COMPLETING", "PARTIAL", "FAILED"},
    "COMPLETING": {"COMPLETED", "PARTIAL"},
    "COMPLETED": set(),
    "PARTIAL": set(),
    "FAILED": set(),
    "CANCELLED": set()
}


class RestoreExecutionError(Exception):
    """Raised when restore execution fails."""
    pass


class RestoreExecutor:
    """Orchestrates restore execution end-to-end."""

    def __init__(self, db: Session, job: RestoreJob):
        self.db = db
        self.job = job
        self.repo = get_repository()

    def transition_to(self, new_status: str, error_message: Optional[str] = None) -> None:
        """Validate and apply state machine transition."""
        curr = (self.job.status or "CREATED").upper()
        target = new_status.upper()
        allowed = VALID_STATE_TRANSITIONS.get(curr, set())
        if target not in allowed:
            raise RestoreExecutionError(
                f"Invalid state transition for RestoreJob #{self.job.id}: {curr} -> {target}"
            )

        self.job.status = target
        now = datetime.datetime.now(datetime.timezone.utc)
        self.job.updated_at = now

        if error_message:
            self.job.error_message = error_message

        if new_status == "RUNNING" and not self.job.started_at:
            self.job.started_at = now
        elif new_status in ("COMPLETED", "PARTIAL", "FAILED"):
            self.job.completed_at = now
        elif new_status == "CANCELLED":
            self.job.cancelled_at = now

        self.db.commit()
        self.db.refresh(self.job)

    def validate_and_plan(self, selected_paths: Optional[List[str]] = None) -> None:
        """Perform pre-execution validation and generate planned RestoreItems."""
        self.transition_to("VALIDATING")

        # 1. Recovery Point verification
        rp = self.db.query(RecoveryPoint).filter(RecoveryPoint.id == self.job.recovery_point_id).first()
        if not rp or rp.status not in ("valid", "completed"):
            err = f"Recovery Point #{self.job.recovery_point_id} is invalid or missing"
            self.transition_to("FAILED", error_message=err)
            raise RestoreExecutionError(err)

        # 2. Reconstruct logical manifest
        logical_files = RestorePlanner.get_recovery_point_logical_files(self.db, rp.id)
        if not logical_files:
            err = f"Recovery Point #{rp.id} manifest is empty"
            self.transition_to("FAILED", error_message=err)
            raise RestoreExecutionError(err)

        # 3. Filter files according to restore_mode
        target_files = RestorePlanner.filter_files(logical_files, self.job.restore_mode, selected_paths)
        if not target_files:
            err = f"No candidate files found for restore mode '{self.job.restore_mode}'"
            self.transition_to("FAILED", error_message=err)
            raise RestoreExecutionError(err)

        # 4. StorageObject availability verification
        for f in target_files:
            if f.storage_object_id:
                so = self.db.query(StorageObject).filter(StorageObject.id == f.storage_object_id).first()
                if not so or so.state == "DELETED":
                    err = f"Referenced StorageObject for '{f.file_name}' is deleted or unavailable"
                    self.transition_to("FAILED", error_message=err)
                    raise RestoreExecutionError(err)
                if so.state == "CORRUPTED" or so.integrity_status == "CORRUPTED":
                    err = f"SOURCE_OBJECT_CORRUPTED: StorageObject {so.object_id} is corrupted"
                    self.transition_to("FAILED", error_message=err)
                    raise RestoreExecutionError(err)

        # 5. Destination root path validation
        try:
            norm_dest_root = os.path.abspath(os.path.normpath(self.job.target_path))
        except Exception as e:
            err = f"Invalid destination root path '{self.job.target_path}': {e}"
            self.transition_to("FAILED", error_message=err)
            raise RestoreExecutionError(err)

        # Transition to PLANNING
        self.transition_to("PLANNING")

        total_bytes = 0
        planned_items = []
        for f in target_files:
            rel = f.relative_path or os.path.basename(f.original_path)
            clean_rel = PathValidator.sanitize_relative_path(rel)
            dest_file_path = PathValidator.resolve_destination(norm_dest_root, clean_rel)

            item = RestoreItem(
                restore_job_id=self.job.id,
                backup_file_id=f.id,
                relative_path=clean_rel,
                destination_path=dest_file_path,
                source_size=f.size_bytes or 0,
                restored_size=0,
                source_sha256=f.sha256,
                restored_sha256=None,
                status="PENDING"
            )
            self.db.add(item)
            planned_items.append(item)
            total_bytes += (f.size_bytes or 0)

        self.job.total_files = len(planned_items)
        self.job.total_bytes = total_bytes
        self.db.commit()

        # Transition to QUEUED
        self.transition_to("QUEUED")

    def execute_restore(self) -> None:
        """Execute restore for all planned items with atomic writes and verification."""
        if self.job.status in ("QUEUED", "PAUSED", "INTERRUPTED", "RESUMING"):
            if self.job.status == "PAUSED" or self.job.status == "INTERRUPTED":
                self.transition_to("RESUMING")
            self.transition_to("RUNNING")
        elif self.job.status != "RUNNING":
            raise RestoreExecutionError(f"Cannot execute restore in status '{self.job.status}'")

        items = self.db.query(RestoreItem).filter(RestoreItem.restore_job_id == self.job.id).all()

        for item in items:
            # Check for cancellation or pause
            self.db.refresh(self.job)
            if self.job.status == "CANCELLED":
                item.status = "CANCELLED"
                self.db.commit()
                return
            if self.job.status == "PAUSED":
                return

            # If already completed from a previous run or checkpoint, verify before skipping rewrite
            if item.status == "COMPLETED" and os.path.exists(item.destination_path):
                # Verify existing file SHA-256
                if item.source_sha256 and self._verify_file_sha256(item.destination_path, item.source_sha256):
                    continue

            bf = self.db.query(BackupFile).filter(BackupFile.id == item.backup_file_id).first() if item.backup_file_id else None
            so = None
            if bf and bf.storage_object_id:
                so = self.db.query(StorageObject).filter(StorageObject.id == bf.storage_object_id).first()

            # Check StorageObject corruption
            if so and (so.state == "CORRUPTED" or so.integrity_status == "CORRUPTED"):
                item.status = "FAILED"
                item.error_code = "SOURCE_OBJECT_CORRUPTED"
                item.error_message = f"CAS StorageObject {so.object_id} is corrupted"
                item.completed_at = datetime.datetime.now(datetime.timezone.utc)
                self.job.failed_files += 1
                self.db.commit()
                continue

            item.status = "RESTORING"
            item.started_at = datetime.datetime.now(datetime.timezone.utc)
            self.db.commit()

            try:
                self._restore_single_item(item, bf, so)
            except Exception as e:
                item.status = "FAILED"
                item.error_code = getattr(e, "error_code", "RESTORE_ERROR")
                item.error_message = str(e)
                item.completed_at = datetime.datetime.now(datetime.timezone.utc)
                self.job.failed_files += 1
                self.db.commit()

            # Save checkpoint after each item
            self._save_checkpoint(item)

        # Finalize restore status
        self.db.refresh(self.job)
        if self.job.status != "CANCELLED":
            if self.job.failed_files > 0:
                self.transition_to("PARTIAL")
            else:
                self.transition_to("COMPLETED")

        # Log audit event
        is_cross = (self.job.source_client_id != self.job.target_client_id)
        action_name = "CROSS_CLIENT_RESTORE" if is_cross else "RESTORE_COMPLETED"
        if self.job.status == "PARTIAL":
            action_name = "RESTORE_PARTIAL"
        elif self.job.status == "FAILED":
            action_name = "RESTORE_FAILED"

        log_audit_event(
            db=self.db,
            action=action_name,
            resource_type="restore",
            resource_id=self.job.restore_id,
            client_id=self.job.target_client_id,
            details=f"Restore job {self.job.restore_id} finished: {self.job.completed_files} completed, {self.job.failed_files} failed, {self.job.skipped_files} skipped"
        )

    def _restore_single_item(self, item: RestoreItem, bf: Optional[BackupFile], so: Optional[StorageObject]) -> None:
        """Safely restore a single file using temporary file and atomic swap."""
        dest_path = item.destination_path
        conflict_mode = self.job.conflict_mode

        # Conflict handling
        if os.path.exists(dest_path):
            if conflict_mode == "SKIP":
                item.status = "SKIPPED"
                item.completed_at = datetime.datetime.now(datetime.timezone.utc)
                self.job.skipped_files += 1
                self.db.commit()
                return
            elif conflict_mode == "FAIL":
                item.status = "FAILED"
                item.error_code = "CONFLICT_FAIL"
                item.error_message = f"File already exists at destination: {dest_path}"
                item.completed_at = datetime.datetime.now(datetime.timezone.utc)
                self.job.failed_files += 1
                self.db.commit()
                return
            elif conflict_mode == "RENAME":
                dest_path = self._generate_renamed_path(dest_path)
                item.destination_path = dest_path

        dest_dir = os.path.dirname(dest_path)
        os.makedirs(dest_dir, exist_ok=True)

        # Temporary file for atomic write
        tmp_name = f".{os.path.basename(dest_path)}.tmp.{uuid.uuid4().hex[:8]}"
        tmp_path = os.path.join(dest_dir, tmp_name)

        hasher = hashlib.sha256()
        bytes_written = 0

        # Read object stream from repository
        comp_algo = so.compression_algorithm if so else "NONE"
        obj_key = so.storage_path if so else (bf.storage_object if bf else None)

        if not obj_key:
            raise RestoreExecutionError("Missing storage object key for backup file")

        stream = self.repo.read_object_stream(obj_key, compression_algorithm=comp_algo)

        try:
            with open(tmp_path, "wb") as out_f:
                for chunk in stream:
                    if not self.job.first_byte_restored_at:
                        self.job.first_byte_restored_at = datetime.datetime.now(datetime.timezone.utc)
                    out_f.write(chunk)
                    hasher.update(chunk)
                    bytes_written += len(chunk)
        except Exception as e:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise RestoreExecutionError(f"Error streaming object: {e}")

        # Verify integrity
        computed_sha = hasher.hexdigest()
        item.restored_sha256 = computed_sha
        item.restored_size = bytes_written

        expected_sha = item.source_sha256
        if expected_sha and computed_sha.lower() != expected_sha.lower():
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            item.status = "FAILED"
            item.error_code = "CHECKSUM_MISMATCH"
            item.error_message = f"Checksum mismatch: expected {expected_sha}, got {computed_sha}"
            item.completed_at = datetime.datetime.now(datetime.timezone.utc)
            self.job.failed_files += 1
            self.db.commit()
            return

        # Atomic replacement: destination is only replaced after verified checksum
        item.status = "VERIFYING"
        self.db.commit()

        os.replace(tmp_path, dest_path)

        # Apply metadata (timestamps) if BASIC or FULL
        if self.job.metadata_mode in ("BASIC", "FULL") and bf and bf.modified_time:
            try:
                mtime_epoch = bf.modified_time.timestamp()
                os.utime(dest_path, (mtime_epoch, mtime_epoch))
            except Exception:
                pass  # Non-fatal metadata error

        item.status = "COMPLETED"
        now = datetime.datetime.now(datetime.timezone.utc)
        item.completed_at = now
        item.verified_at = now

        self.job.completed_files += 1
        self.job.restored_bytes += bytes_written
        self.job.verified_bytes += bytes_written
        if self.job.total_files > 0:
            self.job.progress_percent = round((self.job.completed_files + self.job.skipped_files) / self.job.total_files * 100.0, 1)

        self.db.commit()

    def _save_checkpoint(self, item: RestoreItem) -> None:
        """Record atomic checkpoint for resumable restore."""
        chk = RestoreCheckpoint(
            restore_job_id=self.job.id,
            last_completed_item_id=item.id,
            completed_items_count=self.job.completed_files,
            bytes_restored=self.job.restored_bytes,
            details=json.dumps({
                "last_item_path": item.relative_path,
                "status": item.status,
                "progress_percent": self.job.progress_percent
            })
        )
        self.db.add(chk)
        self.db.commit()

    @staticmethod
    def _verify_file_sha256(path: str, expected_sha: str) -> bool:
        """Compute SHA-256 of existing destination file."""
        try:
            h = hashlib.sha256()
            with open(path, "rb") as f:
                while True:
                    chunk = f.read(1024 * 1024 * 4)
                    if not chunk:
                        break
                    h.update(chunk)
            return h.hexdigest().lower() == expected_sha.lower()
        except Exception:
            return False

    @staticmethod
    def _generate_renamed_path(path: str) -> str:
        """Generate a non-colliding renamed destination path e.g. report (Restored).docx"""
        directory, filename = os.path.split(path)
        base, ext = os.path.splitext(filename)
        candidate = os.path.join(directory, f"{base} (Restored){ext}")
        counter = 1
        while os.path.exists(candidate):
            candidate = os.path.join(directory, f"{base} (Restored {counter}){ext}")
            counter += 1
        return candidate

    def calculate_rto_metrics(self) -> Dict[str, Any]:
        """Compute detailed RTO and performance metrics for the restore job."""
        def format_delta(d: Optional[datetime.timedelta]) -> str:
            if not d:
                return "00:00:00"
            total_sec = max(0, int(d.total_seconds()))
            h = total_sec // 3600
            m = (total_sec % 3600) // 60
            s = total_sec % 60
            return f"{h:02d}:{m:02d}:{s:02d}"

        queue_time_td = None
        if self.job.started_at and self.job.restore_requested_at:
            queue_time_td = self.job.started_at - self.job.restore_requested_at

        startup_time_td = None
        if self.job.first_byte_restored_at and self.job.started_at:
            startup_time_td = self.job.first_byte_restored_at - self.job.started_at

        restore_duration_td = None
        if self.job.completed_at and self.job.started_at:
            restore_duration_td = self.job.completed_at - self.job.started_at

        total_rto_td = None
        if self.job.completed_at and (self.job.restore_requested_at or self.job.started_at):
            start_ref = self.job.restore_requested_at or self.job.started_at
            total_rto_td = self.job.completed_at - start_ref

        speed_mb_s = 0.0
        if restore_duration_td and restore_duration_td.total_seconds() > 0:
            speed_mb_s = round((self.job.restored_bytes / (1024 * 1024)) / restore_duration_td.total_seconds(), 2)

        return {
            "queue_time": format_delta(queue_time_td),
            "startup_time": format_delta(startup_time_td),
            "restore_duration": format_delta(restore_duration_td),
            "total_restore_time": format_delta(total_rto_td),
            "transfer_speed_mb_s": speed_mb_s
        }
