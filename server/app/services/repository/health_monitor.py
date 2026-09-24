"""Repository Health Monitoring Service for RetroVault V7."""

import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from app.models.storage_repository import StorageRepository
from app.models.storage_object import StorageObject
from app.models.recovery_point import RecoveryPoint
from app.models.replication import ReplicationJob
from app.services.repository.provider import get_repository_provider


class RepositoryHealthMonitor:
    """Probes repository availability, tests I/O, verifies capacity, and counts health metrics."""

    def __init__(self, db: Session):
        self.db = db

    def check_repository_health(self, repository_id: int) -> Dict[str, Any]:
        repo = self.db.query(StorageRepository).filter(StorageRepository.id == repository_id).first()
        if not repo:
            raise ValueError(f"StorageRepository #{repository_id} not found")

        provider = get_repository_provider(repo)
        probe = provider.health_check()

        now = datetime.datetime.now(datetime.timezone.utc)
        repo.last_health_check = now
        repo.used_bytes = probe.get("used_bytes", repo.used_bytes)
        repo.available_bytes = probe.get("available_bytes", repo.available_bytes)
        repo.total_bytes = probe.get("total_bytes", repo.total_bytes)

        # Do not overwrite MAINTENANCE mode with probe status unless offline
        if repo.status != "MAINTENANCE":
            repo.status = probe.get("status", repo.status)

        # Additional DB-backed health metrics
        object_count = self.db.query(func.count(StorageObject.id)).scalar() or 0
        corrupted_count = self.db.query(func.count(StorageObject.id)).filter(StorageObject.state == "CORRUPTED").scalar() or 0
        deleting_count = self.db.query(func.count(StorageObject.id)).filter(StorageObject.state == "DELETING").scalar() or 0

        # Last successful backup time
        last_rp = self.db.query(RecoveryPoint).filter(
            RecoveryPoint.status.in_(["valid", "completed"])
        ).order_by(RecoveryPoint.created_at.desc()).first()
        last_backup_time = last_rp.created_at.isoformat() if (last_rp and last_rp.created_at) else None

        # Last successful replication time
        last_repl = self.db.query(ReplicationJob).filter(
            ReplicationJob.status == "COMPLETED",
            (ReplicationJob.source_repository_id == repo.id) | (ReplicationJob.destination_repository_id == repo.id)
        ).order_by(ReplicationJob.completed_at.desc()).first()
        last_repl_time = last_repl.completed_at.isoformat() if (last_repl and last_repl.completed_at) else None

        # Count pending replications
        pending_repl = self.db.query(func.count(ReplicationJob.id)).filter(
            ReplicationJob.status.in_(["CREATED", "QUEUED", "RUNNING", "PAUSED"]),
            (ReplicationJob.source_repository_id == repo.id) | (ReplicationJob.destination_repository_id == repo.id)
        ).scalar() or 0

        self.db.commit()
        self.db.refresh(repo)

        return {
            "repository_id": repo.id,
            "name": repo.name,
            "type": repo.repository_type,
            "status": repo.status,
            "protection_mode": repo.protection_mode,
            "reachable": probe.get("reachable", False),
            "read_test": probe.get("read_test", False),
            "write_test": probe.get("write_test", False),
            "delete_test": probe.get("delete_test", False),
            "latency_ms": probe.get("latency_ms", 0.0),
            "capacity_bytes": repo.total_bytes,
            "used_bytes": repo.used_bytes,
            "available_bytes": repo.available_bytes,
            "free_percent": round((repo.available_bytes / repo.total_bytes * 100), 2) if repo.total_bytes > 0 else 0.0,
            "object_count": object_count,
            "corrupted_object_count": corrupted_count,
            "pending_gc_count": deleting_count,
            "pending_replication_jobs": pending_repl,
            "last_successful_backup": last_backup_time,
            "last_successful_replication": last_repl_time,
            "last_health_check": repo.last_health_check.isoformat() if repo.last_health_check else None,
            "errors": probe.get("errors", [])
        }
