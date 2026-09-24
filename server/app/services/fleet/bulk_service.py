"""Bulk fleet operations service for RetroVault V9."""

import datetime
import json
import uuid
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.cluster_v9_models import BulkOperation, ClusterEvent
from app.models.client import Client
from app.models.backup_job import BackupJob
from app.models.cluster_v9_models import DistributedJob

logger = logging.getLogger(__name__)


class BulkFleetService:
    """Manages fleet-wide bulk operations: policy assignment, bulk triggers, migrations."""

    def __init__(self, db: Session):
        self.db = db

    def trigger_bulk_backup(
        self,
        client_ids: Optional[List[str]] = None,
        job_type: str = "BACKUP",
        priority: str = "NORMAL",
        created_by: Optional[str] = "ADMIN"
    ) -> Dict[str, Any]:
        """Creates distributed jobs to trigger backups across multiple or all active clients."""
        op_id = f"bulk-bkp-{uuid.uuid4().hex[:8]}"
        now = datetime.datetime.now(datetime.timezone.utc)

        # 1. Resolve target clients
        query = self.db.query(Client)
        if client_ids:
            query = query.filter(Client.id.in_(client_ids))
        clients = query.all()

        target_count = len(clients)
        success_count = 0
        failure_count = 0
        created_job_ids = []

        bulk_op = BulkOperation(
            operation_id=op_id,
            operation_type="TRIGGER_BACKUP",
            status="RUNNING",
            target_count=target_count,
            started_at=now,
            created_by=created_by,
        )
        self.db.add(bulk_op)
        self.db.flush()

        priority_weights = {"CRITICAL": 1, "HIGH": 2, "NORMAL": 3, "LOW": 4}
        p_weight = priority_weights.get(priority.upper(), 3)

        for c in clients:
            try:
                # Find an active backup job configuration for client
                bj = self.db.query(BackupJob).filter(BackupJob.client_id == c.id).first()
                d_job = DistributedJob(
                    job_type=job_type.upper(),
                    priority=priority.upper(),
                    priority_weight=p_weight,
                    status="QUEUED",
                    client_id=c.id,
                    repository_id=bj.repository_id if bj else None,
                    payload_json=json.dumps({
                        "trigger_source": "BULK_OPERATION",
                        "bulk_op_id": op_id,
                        "backup_job_id": bj.id if bj else None
                    })
                )
                self.db.add(d_job)
                self.db.flush()
                created_job_ids.append(d_job.id)
                success_count += 1
            except Exception as ex:
                logger.error(f"Failed to queue bulk backup for client {c.id}: {ex}")
                failure_count += 1

        bulk_op.success_count = success_count
        bulk_op.failure_count = failure_count
        bulk_op.status = "COMPLETED" if failure_count == 0 else ("PARTIAL_FAILURE" if success_count > 0 else "FAILED")
        bulk_op.completed_at = datetime.datetime.now(datetime.timezone.utc)
        bulk_op.details_json = json.dumps({"queued_job_ids": created_job_ids})

        ev = ClusterEvent(
            event_type="BULK_OPERATION_COMPLETED",
            severity="INFO" if failure_count == 0 else "WARNING",
            details_json=json.dumps({
                "operation_id": op_id,
                "target_count": target_count,
                "success_count": success_count,
                "failure_count": failure_count
            })
        )
        self.db.add(ev)
        self.db.commit()

        return {
            "operation_id": op_id,
            "status": bulk_op.status,
            "target_count": target_count,
            "success_count": success_count,
            "failure_count": failure_count,
            "job_ids": created_job_ids
        }

    def list_operations(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Lists past bulk operations with metrics."""
        ops = self.db.query(BulkOperation).order_by(BulkOperation.id.desc()).limit(limit).all()
        return [
            {
                "operation_id": o.operation_id,
                "operation_type": o.operation_type,
                "status": o.status,
                "target_count": o.target_count,
                "success_count": o.success_count,
                "failure_count": o.failure_count,
                "skipped_count": o.skipped_count,
                "started_at": o.started_at.isoformat() if o.started_at else None,
                "completed_at": o.completed_at.isoformat() if o.completed_at else None,
                "created_by": o.created_by,
                "details": json.loads(o.details_json) if o.details_json else {}
            }
            for o in ops
        ]
