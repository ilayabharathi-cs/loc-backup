"""CAS-Aware Resumable Replication Engine for RetroVault V7."""

import os
import time
import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from app.models.storage_repository import StorageRepository
from app.models.storage_object import StorageObject
from app.models.recovery_point import RecoveryPoint
from app.models.backup_file import BackupFile
from app.models.replication import ReplicationJob, ReplicationItem, ReplicationCheckpoint
from app.services.repository.provider import get_repository_provider


class ReplicationEngine:
    """Manages planning, streaming, deduplication, checkpointing, and execution of replication jobs."""

    def __init__(self, db: Session, job: ReplicationJob):
        self.db = db
        self.job = job

    def plan_replication(self) -> ReplicationJob:
        """
        Identify required StorageObjects from the target RecoveryPoint (or all active recovery points),
        and build ReplicationItem records.
        """
        self.job.status = "PLANNING"
        self.db.commit()

        # Resolve recovery point runs
        run_ids = []
        if self.job.recovery_point_id:
            rp = self.db.query(RecoveryPoint).filter(RecoveryPoint.id == self.job.recovery_point_id).first()
            if rp:
                run_ids.append(rp.backup_run_id)
                # If incremental, walk baseline runs as well
                curr = rp.run
                while curr and curr.baseline_run_id:
                    run_ids.append(curr.baseline_run_id)
                    from app.models.backup_run import BackupRun
                    curr = self.db.query(BackupRun).filter(BackupRun.id == curr.baseline_run_id).first()
        else:
            active_rps = self.db.query(RecoveryPoint).filter(RecoveryPoint.status.in_(["valid", "completed"])).all()
            run_ids = [r.backup_run_id for r in active_rps if r.backup_run_id]

        # Find distinct StorageObjects
        storage_objects = []
        if run_ids:
            so_stmt = select(StorageObject).where(
                StorageObject.id.in_(
                    select(BackupFile.storage_object_id).where(
                        BackupFile.backup_run_id.in_(run_ids),
                        BackupFile.storage_object_id.isnot(None)
                    )
                ),
                StorageObject.state == "AVAILABLE"
            )
            storage_objects = self.db.execute(so_stmt).scalars().all()
        else:
            # Fallback to all available storage objects
            storage_objects = self.db.query(StorageObject).filter(StorageObject.state == "AVAILABLE").all()

        existing_so_ids = {item.storage_object_id for item in self.job.items if item.storage_object_id}

        new_items = []
        total_bytes = 0
        for so in storage_objects:
            if so.id in existing_so_ids:
                continue
            item = ReplicationItem(
                job_id=self.job.id,
                storage_object_id=so.id,
                source_path=so.storage_path,
                destination_path=so.storage_path,
                stored_sha256=so.stored_sha256,
                content_sha256=so.content_sha256,
                stored_size=so.stored_size,
                status="PENDING",
                retry_count=0
            )
            new_items.append(item)
            total_bytes += so.stored_size

        if new_items:
            self.db.add_all(new_items)

        self.db.flush()
        all_items = self.db.query(ReplicationItem).filter(ReplicationItem.job_id == self.job.id).all()
        self.job.total_objects = len(all_items)
        self.job.total_bytes = sum(i.stored_size for i in all_items)
        self.job.status = "QUEUED"
        self.db.commit()
        self.db.refresh(self.job)
        return self.job

    def execute_replication(self) -> ReplicationJob:
        """Execute the replication pipeline with deduplication, validation, and checkpointing."""
        source_repo = self.db.query(StorageRepository).filter(StorageRepository.id == self.job.source_repository_id).first()
        dest_repo = self.db.query(StorageRepository).filter(StorageRepository.id == self.job.destination_repository_id).first()

        if not source_repo or not dest_repo:
            self.job.status = "FAILED"
            self.job.error_message = "Source or destination repository record not found"
            self.db.commit()
            return self.job

        # Check offline repository state
        if (dest_repo.status or "").upper() == "OFFLINE":
            self.job.status = "QUEUED"
            self.job.error_message = f"Destination repository '{dest_repo.name}' is OFFLINE. Job queued until repository returns online."
            self.db.commit()
            return self.job

        if (source_repo.status or "").upper() == "OFFLINE":
            self.job.status = "QUEUED"
            self.job.error_message = f"Source repository '{source_repo.name}' is OFFLINE. Job queued until repository returns online."
            self.db.commit()
            return self.job

        source_provider = get_repository_provider(source_repo)
        dest_provider = get_repository_provider(dest_repo)

        self.job.status = "RUNNING"
        now = datetime.datetime.now(datetime.timezone.utc)
        if not self.job.started_at:
            self.job.started_at = now
        self.db.commit()

        items = self.db.query(ReplicationItem).filter(
            ReplicationItem.job_id == self.job.id,
            ReplicationItem.status.in_(["PENDING", "IN_PROGRESS", "FAILED"])
        ).order_by(ReplicationItem.id.asc()).all()

        for item in items:
            # Check for cancellation or pause
            self.db.refresh(self.job)
            if self.job.status in ("PAUSED", "CANCELLED"):
                break

            item.status = "IN_PROGRESS"
            self.db.commit()

            try:
                # 1. CAS Deduplication Check: Check if destination already contains verified object
                if dest_provider.exists(item.destination_path):
                    if dest_provider.verify_object(item.destination_path, item.stored_sha256):
                        item.status = "SKIPPED"
                        item.transferred_at = datetime.datetime.now(datetime.timezone.utc)
                        self.job.skipped_objects += 1
                        self.job.completed_objects += 1
                        self._update_progress_and_checkpoint(item.id)
                        continue

                # 2. Retrieve object from source
                data = source_provider.get_object(item.source_path)

                # 3. Bandwidth throttling if configured
                if self.job.bandwidth_limit_mbps and self.job.bandwidth_limit_mbps > 0:
                    limit_bytes_per_sec = self.job.bandwidth_limit_mbps * 1024 * 1024
                    sleep_time = min(0.5, len(data) / limit_bytes_per_sec)
                    if sleep_time > 0.001:
                        time.sleep(sleep_time)

                # 4. Stream to destination repository
                dest_provider.put_object(item.destination_path, data)

                # 5. Verify destination integrity
                if not dest_provider.verify_object(item.destination_path, item.stored_sha256):
                    item.status = "FAILED"
                    item.retry_count += 1
                    item.error_message = f"Checksum verification failed on destination: expected {item.stored_sha256}"
                    self.job.failed_objects += 1
                else:
                    item.status = "COMPLETED"
                    item.transferred_at = datetime.datetime.now(datetime.timezone.utc)
                    self.job.completed_objects += 1
                    self.job.transferred_bytes += len(data)

            except Exception as e:
                item.status = "FAILED"
                item.retry_count += 1
                item.error_message = str(e)
                self.job.failed_objects += 1

            self._update_progress_and_checkpoint(item.id)

        # Final status calculation
        self.db.refresh(self.job)
        if self.job.status not in ("PAUSED", "CANCELLED"):
            if self.job.failed_objects == 0:
                self.job.status = "COMPLETED"
                self.job.progress_percent = 100.0
                self.job.completed_at = datetime.datetime.now(datetime.timezone.utc)
            elif self.job.completed_objects > 0:
                self.job.status = "PARTIAL"
            else:
                self.job.status = "FAILED"

        self.db.commit()
        self.db.refresh(self.job)
        return self.job

    def _update_progress_and_checkpoint(self, last_item_id: int):
        """Update job metrics and record atomic checkpoint."""
        if self.job.total_objects > 0:
            self.job.progress_percent = round((self.job.completed_objects / self.job.total_objects) * 100, 2)
        cp = ReplicationCheckpoint(
            job_id=self.job.id,
            last_completed_item_id=last_item_id,
            completed_objects=self.job.completed_objects,
            transferred_bytes=self.job.transferred_bytes,
            checkpoint_state="ACTIVE"
        )
        self.db.add(cp)
        self.db.commit()

    def pause(self):
        """Pause in-flight replication."""
        self.job.status = "PAUSED"
        self.db.commit()

    def cancel(self):
        """Cancel replication."""
        self.job.status = "CANCELLED"
        self.job.completed_at = datetime.datetime.now(datetime.timezone.utc)
        self.db.commit()

    def retry_failed(self) -> ReplicationJob:
        """Reset failed items back to PENDING and resume."""
        failed_items = self.db.query(ReplicationItem).filter(
            ReplicationItem.job_id == self.job.id,
            ReplicationItem.status == "FAILED"
        ).all()
        for item in failed_items:
            item.status = "PENDING"
            item.error_message = None
        self.job.failed_objects = 0
        self.job.status = "QUEUED"
        self.db.commit()
        return self.execute_replication()
