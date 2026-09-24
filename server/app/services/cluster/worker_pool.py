"""Repository worker pool with backpressure, category isolation, and fair scheduling for RetroVault V9."""

import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.cluster_v9_models import DistributedJob, ClusterNode


class RepositoryWorkerPool:
    """Manages worker pool capacity, backpressure evaluation, and fair queue dispatch."""

    DEFAULT_CATEGORY_CONCURRENCY = {
        "BACKUP": 8,
        "RESTORE": 4,
        "REPLICATION": 4,
        "PRUNE": 2,
        "VERIFICATION": 2,
    }

    BACKPRESSURE_THRESHOLDS = {
        "CRITICAL": 50,  # 50+ queued jobs
        "HIGH": 25,
        "MODERATE": 10,
        "NORMAL": 0,
    }

    def __init__(self, db: Session, category_concurrency: Optional[Dict[str, int]] = None):
        self.db = db
        self.category_concurrency = category_concurrency or self.DEFAULT_CATEGORY_CONCURRENCY

    def get_category_utilization(self) -> Dict[str, Any]:
        """Calculates running vs max concurrency per job category."""
        utilization = {}
        for category, max_limit in self.category_concurrency.items():
            running_count = (
                self.db.query(DistributedJob)
                .filter(
                    DistributedJob.job_type == category,
                    DistributedJob.status.in_(["CLAIMED", "RUNNING"])
                )
                .count()
            )
            queued_count = (
                self.db.query(DistributedJob)
                .filter(
                    DistributedJob.job_type == category,
                    DistributedJob.status == "QUEUED"
                )
                .count()
            )
            utilization[category] = {
                "running": running_count,
                "queued": queued_count,
                "max_concurrency": max_limit,
                "utilization_pct": round((running_count / max_limit) * 100, 1) if max_limit > 0 else 0,
                "is_saturated": running_count >= max_limit
            }
        return utilization

    def evaluate_backpressure(self) -> Dict[str, Any]:
        """Assesses overall cluster queue backlog and node capacity."""
        queued_count = (
            self.db.query(DistributedJob)
            .filter(DistributedJob.status == "QUEUED")
            .count()
        )
        active_nodes_count = (
            self.db.query(ClusterNode)
            .filter(ClusterNode.status.in_(["ACTIVE", "HEALTHY", "READY"]))
            .count()
        )

        level = "NORMAL"
        for thresh_level, thresh_val in self.BACKPRESSURE_THRESHOLDS.items():
            if queued_count >= thresh_val:
                level = thresh_level
                break

        should_throttle_new_jobs = (level in ["HIGH", "CRITICAL"]) or (active_nodes_count == 0)

        return {
            "backpressure_level": level,
            "queued_jobs": queued_count,
            "active_nodes": active_nodes_count,
            "should_throttle_new_jobs": should_throttle_new_jobs,
            "recommended_retry_delay_seconds": 15 if level == "CRITICAL" else (5 if level == "HIGH" else 0)
        }

    def can_accept_job(self, job_type: str, client_id: Optional[str] = None) -> bool:
        """Determines if a new job of given category can be processed immediately without stalling others."""
        bp = self.evaluate_backpressure()
        if bp["should_throttle_new_jobs"] and bp["backpressure_level"] == "CRITICAL":
            return False

        category = job_type.upper()
        max_allowed = self.category_concurrency.get(category, 4)
        current_active = (
            self.db.query(DistributedJob)
            .filter(
                DistributedJob.job_type == category,
                DistributedJob.status.in_(["CLAIMED", "RUNNING"])
            )
            .count()
        )
        return current_active < (max_allowed * 2)  # Allow queuing buffer up to 2x max concurrency
