"""Persistent distributed job queue with atomic claiming and fairness for RetroVault V9."""

import datetime
import json
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_, update

from app.models.cluster_v9_models import DistributedJob, ClusterEvent, ClusterNode

logger = logging.getLogger(__name__)


class DistributedJobQueue:
    """Manages persistent job queue with atomic claims and concurrency enforcement."""

    PRIORITY_WEIGHTS = {
        "CRITICAL": 1,
        "HIGH": 5,
        "NORMAL": 10,
        "LOW": 20
    }

    def __init__(self, db: Session):
        self.db = db

    def enqueue_job(
        self,
        job_type: str,
        priority: str = "NORMAL",
        client_id: Optional[Any] = None,
        repository_id: Optional[int] = None,
        run_id: Optional[int] = None,
        backup_job_id: Optional[int] = None,
        payload: Optional[Dict[str, Any]] = None,
        max_attempts: int = 3
    ) -> DistributedJob:
        """Enqueues a new distributed job into the persistent database queue."""
        priority_norm = priority.upper()
        weight = self.PRIORITY_WEIGHTS.get(priority_norm, 10)
        now = datetime.datetime.now(datetime.timezone.utc)

        job = DistributedJob(
            job_type=job_type.upper(),
            priority=priority_norm,
            priority_weight=weight,
            status="QUEUED",
            client_id=client_id,
            repository_id=repository_id,
            run_id=run_id,
            payload_json=json.dumps(payload or {}),
            max_attempts=max_attempts,
            attempt_count=0,
            available_at=now,
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)

        ev = ClusterEvent(
            event_type="JOB_QUEUED",
            severity="INFO",
            details_json=json.dumps({"job_id": job.id, "job_type": job.job_type, "priority": job.priority})
        )
        self.db.add(ev)
        self.db.commit()
        return job

    def claim_next_job(
        self,
        worker_node_id: str,
        supported_job_types: Optional[List[str]] = None,
        max_client_concurrency: int = 2,
        max_repo_concurrency: int = 4
    ) -> Optional[DistributedJob]:
        """Atomically claims the highest priority eligible job without exceeding concurrency bounds."""
        now = datetime.datetime.now(datetime.timezone.utc)

        # Check worker node health
        node = self.db.query(ClusterNode).filter(ClusterNode.node_id == worker_node_id).first()
        if not node or node.status in ["OFFLINE", "DRAINING", "MAINTENANCE"]:
            return None

        # Build candidate query ordered by priority_weight ascending (1=CRITICAL), then id ascending
        query = (
            self.db.query(DistributedJob)
            .filter(
                DistributedJob.status.in_(["QUEUED", "RETRYING"]),
                DistributedJob.available_at <= now
            )
        )
        if supported_job_types:
            query = query.filter(DistributedJob.job_type.in_([t.upper() for t in supported_job_types]))

        candidates = query.order_by(DistributedJob.priority_weight.asc(), DistributedJob.id.asc()).limit(20).all()

        for candidate in candidates:
            # Concurrency check per client
            if candidate.client_id:
                active_client_jobs = (
                    self.db.query(DistributedJob)
                    .filter(
                        DistributedJob.client_id == candidate.client_id,
                        DistributedJob.status.in_(["CLAIMED", "RUNNING"])
                    )
                    .count()
                )
                if active_client_jobs >= max_client_concurrency:
                    continue

            # Concurrency check per repository
            if candidate.repository_id:
                active_repo_jobs = (
                    self.db.query(DistributedJob)
                    .filter(
                        DistributedJob.repository_id == candidate.repository_id,
                        DistributedJob.status.in_(["CLAIMED", "RUNNING"])
                    )
                    .count()
                )
                if active_repo_jobs >= max_repo_concurrency:
                    continue

            # Atomic claim using compare-and-swap SQL update
            updated = (
                self.db.query(DistributedJob)
                .filter(
                    DistributedJob.id == candidate.id,
                    DistributedJob.status.in_(["QUEUED", "RETRYING"])
                )
                .update({
                    "status": "CLAIMED",
                    "owner_node_id": worker_node_id,
                    "started_at": now,
                    "heartbeat_at": now,
                    "attempt_count": candidate.attempt_count + 1
                }, synchronize_session=False)
            )
            if updated > 0:
                self.db.commit()
                self.db.refresh(candidate)

                ev = ClusterEvent(
                    event_type="JOB_CLAIMED",
                    severity="INFO",
                    node_id=worker_node_id,
                    details_json=json.dumps({"job_id": candidate.id, "job_type": candidate.job_type})
                )
                self.db.add(ev)
                self.db.commit()
                return candidate

        return None

    def heartbeat_job(
        self,
        job_id: int,
        worker_node_id: Optional[str] = None,
        progress_percent: Optional[float] = None,
        status_message: Optional[str] = None
    ) -> bool:
        """Alias for job heartbeat from scheduler API."""
        return self.record_job_heartbeat(job_id, worker_node_id)

    def record_job_heartbeat(self, job_id: int, worker_node_id: Optional[str] = None) -> bool:
        """Updates the heartbeat timestamp for an in-progress job."""
        now = datetime.datetime.now(datetime.timezone.utc)
        query = self.db.query(DistributedJob).filter(
            DistributedJob.id == job_id,
            DistributedJob.status.in_(["CLAIMED", "RUNNING"])
        )
        if worker_node_id:
            query = query.filter(DistributedJob.owner_node_id == worker_node_id)
        updated = query.update({"heartbeat_at": now, "status": "RUNNING"}, synchronize_session=False)
        self.db.commit()
        return updated > 0

    def complete_job(
        self,
        job_id: int,
        worker_node_id: Optional[str] = None,
        status: str = "COMPLETED",
        error_message: Optional[str] = None,
        result_metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Marks a claimed job as COMPLETED, FAILED, or CANCELLED."""
        now = datetime.datetime.now(datetime.timezone.utc)
        query = self.db.query(DistributedJob).filter(DistributedJob.id == job_id)
        if worker_node_id:
            query = query.filter(DistributedJob.owner_node_id == worker_node_id)
        job = query.first()
        if not job:
            return False

        job.status = status.upper()
        job.completed_at = now
        if error_message:
            job.error_message = error_message
        self.db.commit()

        ev = ClusterEvent(
            event_type="JOB_COMPLETED" if job.status == "COMPLETED" else "JOB_FAILED",
            severity="INFO" if job.status == "COMPLETED" else "ERROR",
            node_id=worker_node_id,
            details_json=json.dumps({"job_id": job_id, "status": job.status})
        )
        self.db.add(ev)
        self.db.commit()
        return True

    def fail_job(self, job_id: int, error_message: str, worker_node_id: Optional[str] = None) -> bool:
        """Marks a job as FAILED or schedules RETRYING if attempts remain."""
        job = self.db.query(DistributedJob).filter(DistributedJob.id == job_id).first()
        if not job:
            return False

        now = datetime.datetime.now(datetime.timezone.utc)
        if job.attempt_count < job.max_attempts:
            job.status = "RETRYING"
            job.owner_node_id = None
            job.available_at = now + datetime.timedelta(seconds=5 * job.attempt_count)
            job.error_message = f"Attempt {job.attempt_count} failed: {error_message}"
        else:
            job.status = "FAILED"
            job.completed_at = now
            job.error_message = error_message

        ev = ClusterEvent(
            event_type="JOB_FAILED",
            severity="ERROR",
            node_id=worker_node_id,
            details_json=json.dumps({"job_id": job_id, "status": job.status, "error": error_message})
        )
        self.db.add(ev)
        self.db.commit()
        return True
