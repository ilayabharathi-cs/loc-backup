"""RetroVault V10 Backup Objective & Recovery Telemetry Engine (RPO / RTO).

Tracks factual backup intervals, observed RPO, backup freshness, and measured RTO
against configured targets. Never claims or promises recovery guarantees.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select, desc, func
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.backup_job import BackupJob
from app.models.backup_run import BackupRun
from app.models.backup_policy import BackupPolicy
from app.models.restore_job import RestoreJob

logger = logging.getLogger(__name__)


class BackupObjectiveMonitor:
    """Monitors client-level RPO adherence and restore RTO telemetry."""

    def __init__(self, db: Session):
        self.db = db

    def evaluate_client_rpo(self, client_id: str) -> Dict[str, Any]:
        """Evaluate factual RPO attainment for a specific client."""
        client = self.db.scalar(select(Client).where(Client.client_id == client_id))
        if not client:
            return {
                "client_id": client_id,
                "status": "UNKNOWN",
                "reason": "Client not found in system database"
            }

        # Find active backup policies for this client
        job = self.db.scalar(
            select(BackupJob).where(BackupJob.client_id == client.id).limit(1)
        )
        rpo_target_hours = 24.0  # default target: 24h RPO
        if job and job.policy_id:
            policy = self.db.scalar(select(BackupPolicy).where(BackupPolicy.id == job.policy_id))
            if policy and hasattr(policy, "rpo_target_hours") and policy.rpo_target_hours:
                rpo_target_hours = float(policy.rpo_target_hours)

        # Retrieve last successful backup run
        last_success_run = self.db.scalar(
            select(BackupRun)
            .join(BackupJob, BackupRun.job_id == BackupJob.id)
            .where(BackupJob.client_id == client.id, func.upper(BackupRun.status).in_(["SUCCESS", "COMPLETED"]))
            .order_by(desc(BackupRun.completed_at))
            .limit(1)
        )

        now = datetime.now(timezone.utc)
        if not last_success_run or not last_success_run.completed_at:
            return {
                "client_id": client.client_id,
                "hostname": client.hostname,
                "rpo_target_hours": rpo_target_hours,
                "observed_rpo_hours": None,
                "last_success": None,
                "next_expected": None,
                "status": "UNKNOWN",
                "backup_freshness_seconds": None,
                "missed_objective": False,
                "reason": "No successful backup runs recorded yet for this client"
            }

        completed_at = last_success_run.completed_at
        if completed_at.tzinfo is None:
            completed_at = completed_at.replace(tzinfo=timezone.utc)

        freshness_sec = (now - completed_at).total_seconds()
        observed_rpo_hours = freshness_sec / 3600.0
        next_expected = completed_at + timedelta(hours=rpo_target_hours)

        # Categorize status based strictly on measured values
        if observed_rpo_hours <= rpo_target_hours:
            status = "MEETING"
            missed = False
        elif observed_rpo_hours <= (rpo_target_hours * 1.25):
            status = "AT_RISK"
            missed = False
        else:
            status = "MISSED"
            missed = True

        duration_sec = 0.0
        if last_success_run.started_at and last_success_run.completed_at:
            duration_sec = (last_success_run.completed_at - last_success_run.started_at).total_seconds()

        return {
            "client_id": client.client_id,
            "hostname": client.hostname,
            "rpo_target_hours": rpo_target_hours,
            "observed_rpo_hours": round(observed_rpo_hours, 2),
            "last_success": completed_at.isoformat(),
            "next_expected": next_expected.isoformat(),
            "backup_freshness_seconds": round(freshness_sec, 1),
            "missed_objective": missed,
            "backup_duration_seconds": round(duration_sec, 2),
            "data_changed_bytes": getattr(last_success_run, "bytes_uploaded", 0) or 0,
            "status": status,
            "measured_at": now.isoformat()
        }

    def evaluate_fleet_rpo(self, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Evaluate RPO status across all registered agent clients with pagination."""
        clients = list(self.db.scalars(
            select(Client).offset(offset).limit(limit)
        ).all())

        summary = {"MEETING": 0, "AT_RISK": 0, "MISSED": 0, "UNKNOWN": 0}
        results = []

        for c in clients:
            item = self.evaluate_client_rpo(c.client_id)
            st = item.get("status", "UNKNOWN")
            summary[st] = summary.get(st, 0) + 1
            results.append(item)

        return {
            "total_evaluated": len(clients),
            "summary": summary,
            "clients": results
        }

    def evaluate_rto_telemetry(self, restore_job_id: int) -> Dict[str, Any]:
        """Calculate factual measured RTO for a completed restore execution."""
        job = self.db.scalar(select(RestoreJob).where(RestoreJob.id == restore_job_id))
        if not job:
            return {"error": "Restore job not found"}

        started = job.started_at
        completed = job.completed_at
        dur = 0.0
        if started and completed:
            dur = (completed - started).total_seconds()

        bytes_restored = job.restored_bytes or 0
        files_restored = job.completed_files or 0
        mb_restored = bytes_restored / (1024.0 * 1024.0)
        throughput = round(mb_restored / dur, 2) if dur > 0 else 0.0

        target_rto_hours = 4.0  # reference target objective

        return {
            "restore_job_id": job.id,
            "status": job.status,
            "restore_started_at": started.isoformat() if started else None,
            "restore_completed_at": completed.isoformat() if completed else None,
            "restore_duration_seconds": round(dur, 2),
            "observed_rto_minutes": round(dur / 60.0, 2),
            "configured_target_rto_hours": target_rto_hours,
            "bytes_restored": bytes_restored,
            "files_restored": files_restored,
            "throughput_mb_s": throughput,
            "disclaimer": "Measured actual recovery duration. Not a forward-looking recovery guarantee."
        }
