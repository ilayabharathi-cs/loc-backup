"""Cluster reconciliation service for RetroVault V9.

Executed exclusively by the active cluster leader to maintain overall cluster health,
reconcile dead nodes, trigger orphan recovery, clean expired locks, and balance workloads.
"""

import datetime
import json
import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.cluster_v9_models import (
    ClusterNode,
    ClusterLease,
    DistributedJob,
    DistributedLock,
    ClusterEvent,
)
from app.services.cluster.node_service import NodeHeartbeatService
from app.services.cluster.orphan_recovery import OrphanRecoveryService

logger = logging.getLogger(__name__)


class ClusterReconciliationService:
    """Performs cluster-wide health checks and cleanup.
    
    Guaranteed to run safely ONLY if the calling node holds the active leadership lease.
    """

    def __init__(self, db: Session, leader_node_id: str):
        self.db = db
        self.leader_node_id = leader_node_id

    def reconcile_cluster(self, force: bool = False) -> Dict[str, Any]:
        """Executes a full reconciliation cycle if calling node is the active leader."""
        now = datetime.datetime.now(datetime.timezone.utc)

        # 1. Split-brain safeguard: verify leadership lease
        if not force:
            lease = (
                self.db.query(ClusterLease)
                .filter(ClusterLease.lease_key == "LEADER_ELECTION")
                .first()
            )
            if not lease or lease.owner_node_id != self.leader_node_id:
                return {
                    "reconciled": False,
                    "reason": f"Node {self.leader_node_id} is not the active leader"
                }
            lease_exp = lease.lease_expires_at
            if lease_exp.tzinfo is None:
                lease_exp = lease_exp.replace(tzinfo=datetime.timezone.utc)
            if now > lease_exp:
                return {
                    "reconciled": False,
                    "reason": "Leadership lease has expired"
                }

        reconciliation_summary: Dict[str, Any] = {
            "reconciled": True,
            "timestamp": now.isoformat(),
            "leader_node_id": self.leader_node_id,
        }

        # 2. Node health reconciliation (mark nodes whose heartbeats have expired)
        node_service = NodeHeartbeatService(self.db)
        node_summary = node_service.reap_offline_nodes(timeout_seconds=30)
        reconciliation_summary["nodes"] = node_summary

        # 3. Orphan job recovery (jobs assigned to offline nodes or with stale heartbeats)
        orphan_service = OrphanRecoveryService(self.db)
        orphan_summary = orphan_service.scan_and_recover_orphaned_jobs(heartbeat_timeout_seconds=45)
        reconciliation_summary["orphans"] = orphan_summary

        # 4. Clean expired distributed locks
        expired_locks_count = self._clean_expired_locks(now)
        reconciliation_summary["expired_locks_cleared"] = expired_locks_count

        # 5. Priority aging: prevent starvation of lower-priority queued jobs
        aged_jobs_count = self._age_stagnant_jobs(now, age_threshold_seconds=120)
        reconciliation_summary["aged_jobs_promoted"] = aged_jobs_count

        # 6. Log reconciliation audit event
        ev = ClusterEvent(
            event_type="CLUSTER_RECONCILED",
            severity="INFO",
            node_id=self.leader_node_id,
            details_json=json.dumps(reconciliation_summary)
        )
        self.db.add(ev)
        self.db.commit()

        return reconciliation_summary

    def _clean_expired_locks(self, now: datetime.datetime) -> int:
        """Removes expired locks from distributed_locks table."""
        expired = (
            self.db.query(DistributedLock)
            .filter(DistributedLock.expires_at < now)
            .delete(synchronize_session=False)
        )
        if expired > 0:
            self.db.commit()
        return expired

    def _age_stagnant_jobs(self, now: datetime.datetime, age_threshold_seconds: int = 120) -> int:
        """Promotes jobs that have been queued longer than age_threshold_seconds to prevent starvation."""
        cutoff = now - datetime.timedelta(seconds=age_threshold_seconds)
        stagnant_jobs = (
            self.db.query(DistributedJob)
            .filter(
                DistributedJob.status == "QUEUED",
                DistributedJob.created_at <= cutoff,
                DistributedJob.priority_weight > 1  # Not already CRITICAL
            )
            .all()
        )
        promoted = 0
        for job in stagnant_jobs:
            job.priority_weight = max(1, job.priority_weight - 1)
            promoted += 1

        if promoted > 0:
            self.db.commit()
        return promoted
