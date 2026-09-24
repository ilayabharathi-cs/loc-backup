"""Two-Phase Safe Garbage Collector for RetroVault V5 Storage Engine.

Performs reference tracking across all clients and recovery points:
Phase 1: Mark candidate objects (AVAILABLE -> DELETING)
Phase 2: Sweep & safely physically remove from disk (DELETING -> DELETED)
Includes crash reconciliation and dry-run simulation.
"""

import datetime
import os
import uuid
from typing import Dict, List, Optional, Set, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func, not_

from app.models.storage_object import StorageObject
from app.models.backup_file import BackupFile
from app.models.recovery_point import RecoveryPoint
from app.models.garbage_collection import GarbageCollectionJob, GarbageCollectionItem
from app.services.repository.local import get_repository


class GarbageCollector:
    """Safely reclaims orphaned physical storage objects."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = get_repository()

    def get_active_referenced_storage_ids(self) -> Set[int]:
        """
        Query all StorageObject IDs that are currently referenced by:
        1. Any valid, active (non-expired) Recovery Point across all clients.
        2. Any active (pending/running) backup runs or upload sessions.
        """
        # 1. Recovery points that are active or protected (retention_status == 'active' OR protection_state != 'NORMAL' OR security_hold_until > now)
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        active_rp_subquery = select(RecoveryPoint.backup_run_id).where(
            RecoveryPoint.status.in_(["valid", "completed"]),
            (
                (RecoveryPoint.retention_status == "active") |
                (RecoveryPoint.protection_state.in_(["PROTECTED", "RETENTION_LOCKED", "SECURITY_HOLD", "QUARANTINED"])) |
                (RecoveryPoint.security_hold_until > now_utc)
            )
        )

        # Storage object IDs referenced by files in active recovery points
        referenced_stmt = select(BackupFile.storage_object_id).where(
            BackupFile.backup_run_id.in_(active_rp_subquery),
            BackupFile.storage_object_id.isnot(None),
        ).distinct()

        active_obj_ids = set(self.db.execute(referenced_stmt).scalars().all())

        # 2. Also protect files from the newest completed recovery point per client even if retention hasn't evaluated
        latest_rp_stmt = select(RecoveryPoint.backup_run_id).order_by(RecoveryPoint.created_at.desc()).limit(1)
        latest_run_id = self.db.execute(latest_rp_stmt).scalar_one_or_none()
        if latest_run_id:
            latest_files_stmt = select(BackupFile.storage_object_id).where(
                BackupFile.backup_run_id == latest_run_id,
                BackupFile.storage_object_id.isnot(None),
            ).distinct()
            active_obj_ids.update(self.db.execute(latest_files_stmt).scalars().all())

        # 3. Protect StorageObjects referenced by any active restore job
        from app.models.restore_job import RestoreJob
        active_statuses = [
            "pending", "running", "CREATED", "VALIDATING", "PLANNING",
            "QUEUED", "RUNNING", "PAUSED", "RESUMING", "VERIFYING"
        ]
        active_restore_rp_subquery = select(RestoreJob.recovery_point_id).where(
            RestoreJob.status.in_(active_statuses)
        )
        active_restore_run_subquery = select(RecoveryPoint.backup_run_id).where(
            RecoveryPoint.id.in_(active_restore_rp_subquery)
        )
        active_restore_stmt = select(BackupFile.storage_object_id).where(
            BackupFile.backup_run_id.in_(active_restore_run_subquery),
            BackupFile.storage_object_id.isnot(None)
        ).distinct()
        active_obj_ids.update(self.db.execute(active_restore_stmt).scalars().all())

        # 4. Protect StorageObjects referenced by any active replication job
        try:
            from app.models.replication import ReplicationJob, ReplicationItem
            active_repl_statuses = ["CREATED", "PLANNING", "QUEUED", "RUNNING", "PAUSED", "RESUMING", "VERIFYING"]
            active_repl_subquery = select(ReplicationJob.id).where(ReplicationJob.status.in_(active_repl_statuses))
            active_repl_stmt = select(ReplicationItem.storage_object_id).where(
                ReplicationItem.job_id.in_(active_repl_subquery),
                ReplicationItem.storage_object_id.isnot(None)
            ).distinct()
            active_obj_ids.update(self.db.execute(active_repl_stmt).scalars().all())
        except Exception:
            pass

        result_ids: Set[Any] = set()
        for x in active_obj_ids:
            if x is not None:
                try:
                    result_ids.add(int(x))
                    result_ids.add(str(x))
                except (ValueError, TypeError):
                    result_ids.add(x)
        return result_ids

    def run_garbage_collection(self, dry_run: bool = False) -> GarbageCollectionJob:
        """
        Execute two-phase garbage collection pass.
        If dry_run=True, simulates the pass and calculates reclaimable space without modifying storage.
        """
        job_id = f"gc_{uuid.uuid4().hex[:12]}"
        job = GarbageCollectionJob(
            job_id=job_id,
            status="running" if not dry_run else "simulated",
            started_at=datetime.datetime.now(datetime.timezone.utc),
            candidates_found=0,
            objects_deleted=0,
            objects_skipped=0,
            bytes_reclaimed=0,
        )
        self.db.add(job)
        self.db.flush()

        try:
            active_obj_ids = self.get_active_referenced_storage_ids()

            # Find candidate StorageObjects that are AVAILABLE or DELETING, but not in active_obj_ids
            candidates_stmt = select(StorageObject).where(
                StorageObject.state.in_(["AVAILABLE", "DELETING"]),
                not_(StorageObject.id.in_(active_obj_ids)) if active_obj_ids else True,
            )
            candidate_objects = self.db.execute(candidates_stmt).scalars().all()
            job.candidates_found = len(candidate_objects)

            if dry_run:
                # Calculate simulated space savings
                total_bytes = sum(obj.stored_size for obj in candidate_objects)
                job.bytes_reclaimed = total_bytes
                job.objects_deleted = len(candidate_objects)
                job.status = "completed"
                job.completed_at = datetime.datetime.now(datetime.timezone.utc)
                self.db.commit()
                return job

            # Phase 1: Mark & Verify (state -> DELETING)
            items_to_sweep: List[Tuple[GarbageCollectionItem, StorageObject]] = []
            for obj in candidate_objects:
                # Double-check references
                ref_count_check = self.db.execute(
                    select(func.count(BackupFile.id)).where(
                        BackupFile.storage_object_id == obj.id,
                        BackupFile.backup_run_id.in_(
                            select(RecoveryPoint.backup_run_id).where(
                                RecoveryPoint.retention_status == "active"
                            )
                        ),
                    )
                ).scalar_one()

                if ref_count_check > 0:
                    job.objects_skipped += 1
                    continue

                obj.state = "DELETING"
                item = GarbageCollectionItem(
                    gc_job_id=job.id,
                    storage_object_id=obj.id,
                    object_sha256=obj.content_sha256,
                    stored_size=obj.stored_size,
                    status="marked",
                    reason="No active recovery point references",
                )
                self.db.add(item)
                items_to_sweep.append((item, obj))

            self.db.flush()

            # Phase 2: Sweep & Physical Deletion
            for item, obj in items_to_sweep:
                item.status = "deleting"
                self.db.flush()

                # Physical file removal
                storage_path = obj.storage_path
                physically_removed = self.repo.physical_delete_object(storage_path)

                # Update database records
                obj.state = "DELETED"
                obj.reference_count = 0
                item.status = "deleted"
                job.objects_deleted += 1
                job.bytes_reclaimed += obj.stored_size

            job.status = "completed"
            job.completed_at = datetime.datetime.now(datetime.timezone.utc)
            self.db.commit()
            return job

        except Exception as e:
            self.db.rollback()
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.datetime.now(datetime.timezone.utc)
            self.db.add(job)
            self.db.commit()
            raise

    def reconcile_startup_state(self) -> int:
        """
        Crash recovery reconciliation:
        Checks for any StorageObjects stranded in DELETING state.
        If an active recovery point references it, reset to AVAILABLE; otherwise delete physically.
        """
        stranded_stmt = select(StorageObject).where(StorageObject.state == "DELETING")
        stranded = self.db.execute(stranded_stmt).scalars().all()
        if not stranded:
            return 0

        active_obj_ids = self.get_active_referenced_storage_ids()
        reconciled_count = 0

        for obj in stranded:
            if obj.id in active_obj_ids:
                obj.state = "AVAILABLE"
            else:
                self.repo.physical_delete_object(obj.storage_path)
                obj.state = "DELETED"
                obj.reference_count = 0
            reconciled_count += 1

        self.db.commit()
        return reconciled_count
