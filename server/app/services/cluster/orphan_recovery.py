"""Orphan job recovery and worker crash reconciliation for RetroVault V9."""

import datetime
import json
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.cluster_v9_models import DistributedJob, ClusterNode, ClusterEvent
from app.models.backup_run import BackupRun

logger = logging.getLogger(__name__)


class OrphanRecoveryService:
    """Detects and safely recovers abandoned jobs from crashed or offline worker nodes."""

    DEFAULT_HEARTBEAT_TIMEOUT_SECONDS = 45

    def __init__(self, db: Session):
        self.db = db

    def scan_and_recover_orphaned_jobs(
        self,
        heartbeat_timeout_seconds: Optional[int] = None
    ) -> Dict[str, Any]:
        """Identifies running/claimed jobs with dead worker nodes or stale job heartbeats."""
        timeout_sec = heartbeat_timeout_seconds or self.DEFAULT_HEARTBEAT_TIMEOUT_SECONDS
        now = datetime.datetime.now(datetime.timezone.utc)

        # 1. Query all active jobs
        active_jobs = (
            self.db.query(DistributedJob)
            .filter(DistributedJob.status.in_(["CLAIMED", "RUNNING"]))
            .all()
        )

        orphaned_count = 0
        requeued_count = 0
        failed_count = 0
        recovered_job_ids = []

        for job in active_jobs:
            is_orphan = False
            orphan_reason = ""

            # Check owner node status
            if job.owner_node_id:
                owner_node = self.db.query(ClusterNode).filter(ClusterNode.node_id == job.owner_node_id).first()
                if not owner_node or owner_node.status in ["OFFLINE", "UNKNOWN"]:
                    is_orphan = True
                    orphan_reason = f"Owner node {job.owner_node_id} is OFFLINE or missing"

            # Check heartbeat staleness
            if not is_orphan and job.heartbeat_at:
                hb = job.heartbeat_at
                if hb.tzinfo is None:
                    hb = hb.replace(tzinfo=datetime.timezone.utc)
                if (now - hb).total_seconds() >= timeout_sec:
                    is_orphan = True
                    orphan_reason = f"Heartbeat missed for {(now - hb).total_seconds():.1f}s"

            if is_orphan:
                orphaned_count += 1
                job.status = "ORPHANED"
                job.error_message = f"Orphaned: {orphan_reason}"

                ev = ClusterEvent(
                    event_type="JOB_ORPHANED",
                    severity="WARNING",
                    node_id=job.owner_node_id,
                    details_json=json.dumps({"job_id": job.id, "reason": orphan_reason})
                )
                self.db.add(ev)

                # Recover/Requeue if within retry budget
                if job.attempt_count < job.max_attempts:
                    job.status = "QUEUED"
                    job.owner_node_id = None
                    job.heartbeat_at = None
                    job.available_at = now + datetime.timedelta(seconds=2)
                    requeued_count += 1
                    recovered_job_ids.append(job.id)

                    ev_rq = ClusterEvent(
                        event_type="JOB_REQUEUED",
                        severity="INFO",
                        details_json=json.dumps({"job_id": job.id, "new_status": "QUEUED"})
                    )
                    self.db.add(ev_rq)
                else:
                    job.status = "FAILED"
                    job.completed_at = now
                    failed_count += 1

        self.db.commit()
        return {
            "scanned_active_jobs": len(active_jobs),
            "orphaned_count": orphaned_count,
            "requeued_count": requeued_count,
            "failed_count": failed_count,
            "recovered_job_ids": recovered_job_ids
        }
