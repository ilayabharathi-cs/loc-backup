"""Retention Engine for evaluating recovery points and managing backup lifecycles (RetroVault V5).

Evaluates recovery points against configured Retention Policies and GFS rules.
Flags points as 'active' or 'expired'. Does NOT physically delete files;
physical cleanup is strictly managed by Two-Phase Garbage Collection.
"""

import json
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.recovery_point import RecoveryPoint
from app.models.retention_policy import RetentionPolicy, RetentionEvaluation
from app.models.restore_job import RestoreJob
from app.services.retention.gfs_selector import GFSSelector


class RetentionEngine:
    """Executes safe retention evaluation and lifecycle classification."""

    @staticmethod
    def evaluate_policy(
        db: Session,
        retention_policy_id: Optional[int] = None,
        client_id: Optional[int] = None,
    ) -> List[RetentionEvaluation]:
        """
        Evaluate retention for one or all active retention policies.
        Returns the created RetentionEvaluation logs.
        """
        # Determine policies to evaluate
        query = select(RetentionPolicy).where(RetentionPolicy.is_active == True)
        if retention_policy_id:
            query = query.where(RetentionPolicy.id == retention_policy_id)

        policies = db.execute(query).scalars().all()
        if not policies:
            # If no explicit retention policy exists yet, return empty list
            return []

        # Find active restore job recovery point IDs (to protect)
        active_statuses = [
            "pending", "running", "CREATED", "VALIDATING", "PLANNING",
            "QUEUED", "RUNNING", "PAUSED", "RESUMING", "VERIFYING"
        ]
        active_restore_stmt = select(RestoreJob.recovery_point_id).where(
            RestoreJob.status.in_(active_statuses)
        )
        active_restore_rp_ids = set(db.execute(active_restore_stmt).scalars().all())

        evaluation_records = []

        for policy in policies:
            # Gather recovery points associated with this policy (via policy_id) or all if policy_id is null
            rp_query = select(RecoveryPoint).where(RecoveryPoint.status.in_(["valid", "completed"]))
            if policy.policy_id:
                from app.models.backup_run import BackupRun
                rp_query = rp_query.join(BackupRun, RecoveryPoint.backup_run_id == BackupRun.id).where(
                    BackupRun.policy_id == policy.policy_id
                )
            if client_id:
                rp_query = rp_query.where(RecoveryPoint.client_id == client_id)

            recovery_points = db.execute(rp_query).scalars().all()
            if not recovery_points:
                eval_record = RetentionEvaluation(
                    retention_policy_id=policy.id,
                    total_recovery_points=0,
                    protected_count=0,
                    expired_count=0,
                    reclaimed_bytes=0,
                    details=json.dumps({"info": "No completed recovery points found"}),
                )
                db.add(eval_record)
                evaluation_records.append(eval_record)
                continue

            selector = GFSSelector(
                keep_last=policy.keep_last,
                daily_count=policy.daily,
                weekly_count=policy.weekly,
                monthly_count=policy.monthly,
                yearly_count=policy.yearly,
                timezone_name=policy.timezone or "UTC",
            )

            decisions = selector.evaluate_points(recovery_points)

            protected_count = 0
            expired_count = 0
            details_list = []

            for rp in recovery_points:
                dec = decisions.get(rp.id)
                if not dec:
                    continue

                # Safety check: Active restore job protection
                if rp.id in active_restore_rp_ids:
                    dec["keep"] = True
                    dec["tier"] = "RESTORE_ACTIVE"
                    dec["reason"] = "Protected by active restore job"

                if dec["keep"]:
                    rp.retention_status = "active"
                    rp.retention_tier = dec["tier"]
                    rp.is_daily = dec["is_daily"]
                    rp.is_weekly = dec["is_weekly"]
                    rp.is_monthly = dec["is_monthly"]
                    rp.is_yearly = dec["is_yearly"]
                    protected_count += 1
                else:
                    rp.retention_status = "expired"
                    rp.retention_tier = "EXPIRED"
                    rp.is_daily = False
                    rp.is_weekly = False
                    rp.is_monthly = False
                    rp.is_yearly = False
                    expired_count += 1

                details_list.append({
                    "recovery_point_id": rp.id,
                    "point_id": f"RP-{rp.id}",
                    "created_at": rp.created_at.isoformat() if rp.created_at else None,
                    "retention_status": rp.retention_status,
                    "tier": rp.retention_tier,
                    "reason": dec["reason"],
                })

            eval_record = RetentionEvaluation(
                retention_policy_id=policy.id,
                total_recovery_points=len(recovery_points),
                protected_count=protected_count,
                expired_count=expired_count,
                reclaimed_bytes=0,  # Bytes are reclaimed during GC
                details=json.dumps({"decisions": details_list}),
            )
            db.add(eval_record)
            evaluation_records.append(eval_record)

        db.commit()
        return evaluation_records

    @staticmethod
    def toggle_manual_protection(db: Session, recovery_point_id: int, protect: bool) -> Optional[RecoveryPoint]:
        """Explicitly protect or unprotect a recovery point from expiration."""
        rp = db.get(RecoveryPoint, recovery_point_id)
        if not rp:
            return None
        rp.is_manual_protected = protect
        if protect:
            rp.retention_status = "active"
            rp.retention_tier = "MANUAL"
        db.commit()
        db.refresh(rp)
        return rp
