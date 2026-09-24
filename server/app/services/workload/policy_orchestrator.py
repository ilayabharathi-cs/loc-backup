"""RetroVault V11: Policy Lifecycle and Orchestration Service."""

import json
import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.models.workload_v11_models import PolicyLifecycle, PolicyApproval, Workload, WorkloadProtection
from app.models.client import Client
from app.models.audit_log import AuditLog


LIFECYCLE_DRAFT = "DRAFT"
LIFECYCLE_VALIDATING = "VALIDATING"
LIFECYCLE_APPROVED = "APPROVED"
LIFECYCLE_ACTIVE = "ACTIVE"
LIFECYCLE_SUSPENDED = "SUSPENDED"
LIFECYCLE_RETIRED = "RETIRED"


class PolicyOrchestrationService:
    """Manages immutable versioning, approvals, rollbacks, and lifecycle of backup policies."""

    def __init__(self, db: Session):
        self.db = db

    def create_policy_version(
        self,
        policy_id: str,
        definition: Dict[str, Any],
        created_by: str = "ADMIN"
    ) -> PolicyLifecycle:
        """Create a new DRAFT version for a policy (never modifies active policy in-place)."""
        now = datetime.datetime.now(datetime.timezone.utc)
        # Find highest existing version
        stmt = select(func.max(PolicyLifecycle.version)).where(PolicyLifecycle.policy_id == policy_id)
        current_max = self.db.execute(stmt).scalar() or 0
        new_version = current_max + 1

        lifecycle = PolicyLifecycle(
            policy_id=policy_id,
            version=new_version,
            lifecycle_state=LIFECYCLE_DRAFT,
            definition_json=json.dumps(definition),
            created_by=created_by,
            created_at=now,
            updated_at=now
        )
        self.db.add(lifecycle)
        self.db.commit()
        self.db.refresh(lifecycle)

        self._record_audit(
            action="POLICY_DRAFT_CREATED",
            policy_id=policy_id,
            user=created_by,
            details=f"Created policy {policy_id} version {new_version} in DRAFT state"
        )
        return lifecycle

    def approve_policy_version(
        self,
        policy_lifecycle_id: int,
        approver: str,
        notes: Optional[str] = None
    ) -> PolicyLifecycle:
        """Sign off on a policy lifecycle version, transitioning to APPROVED."""
        stmt = select(PolicyLifecycle).where(PolicyLifecycle.id == policy_lifecycle_id)
        lifecycle = self.db.execute(stmt).scalars().first()
        if not lifecycle:
            raise ValueError(f"PolicyLifecycle {policy_lifecycle_id} not found")

        now = datetime.datetime.now(datetime.timezone.utc)
        approval = PolicyApproval(
            policy_lifecycle_id=lifecycle.id,
            requested_by=lifecycle.created_by,
            approved_by=approver,
            status="APPROVED",
            approval_notes=notes,
            approved_at=now
        )
        self.db.add(approval)

        lifecycle.lifecycle_state = LIFECYCLE_APPROVED
        lifecycle.updated_at = now
        self.db.commit()
        self.db.refresh(lifecycle)

        self._record_audit(
            action="POLICY_APPROVED",
            policy_id=lifecycle.policy_id,
            user=approver,
            details=f"Approved policy {lifecycle.policy_id} version {lifecycle.version}"
        )
        return lifecycle

    def activate_policy_version(self, policy_lifecycle_id: int, activated_by: str = "ADMIN") -> PolicyLifecycle:
        """Promote an APPROVED policy version to ACTIVE and retire previous active versions."""
        stmt = select(PolicyLifecycle).where(PolicyLifecycle.id == policy_lifecycle_id)
        lifecycle = self.db.execute(stmt).scalars().first()
        if not lifecycle:
            raise ValueError(f"PolicyLifecycle {policy_lifecycle_id} not found")
        if lifecycle.lifecycle_state != LIFECYCLE_APPROVED:
            raise ValueError(f"Cannot activate policy in state '{lifecycle.lifecycle_state}'; must be APPROVED first")

        now = datetime.datetime.now(datetime.timezone.utc)

        # Retire currently active versions of this policy
        active_stmt = select(PolicyLifecycle).where(
            PolicyLifecycle.policy_id == lifecycle.policy_id,
            PolicyLifecycle.lifecycle_state == LIFECYCLE_ACTIVE
        )
        active_versions = self.db.execute(active_stmt).scalars().all()
        for v in active_versions:
            v.lifecycle_state = LIFECYCLE_RETIRED
            v.updated_at = now

        lifecycle.lifecycle_state = LIFECYCLE_ACTIVE
        lifecycle.effective_at = now
        lifecycle.updated_at = now
        self.db.commit()
        self.db.refresh(lifecycle)

        self._record_audit(
            action="POLICY_ACTIVATED",
            policy_id=lifecycle.policy_id,
            user=activated_by,
            details=f"Activated policy {lifecycle.policy_id} version {lifecycle.version}"
        )
        return lifecycle

    def rollback_policy(self, policy_id: str, target_version: int, rolled_back_by: str = "ADMIN") -> PolicyLifecycle:
        """Roll back to an earlier verified version by copying it into a newly approved version."""
        stmt = select(PolicyLifecycle).where(
            PolicyLifecycle.policy_id == policy_id,
            PolicyLifecycle.version == target_version
        )
        target = self.db.execute(stmt).scalars().first()
        if not target:
            raise ValueError(f"Policy {policy_id} version {target_version} does not exist for rollback")

        definition = json.loads(target.definition_json)
        # Create new version with target definition and activate it
        new_version_lc = self.create_policy_version(policy_id, definition, created_by=f"ROLLBACK:{rolled_back_by}")
        self.approve_policy_version(new_version_lc.id, approver=rolled_back_by, notes=f"Rollback to v{target_version}")
        active_lc = self.activate_policy_version(new_version_lc.id, activated_by=rolled_back_by)

        self._record_audit(
            action="POLICY_ROLLED_BACK",
            policy_id=policy_id,
            user=rolled_back_by,
            details=f"Rolled back policy {policy_id} to configuration of v{target_version} as new v{active_lc.version}"
        )
        return active_lc

    def calculate_affected_resources(self, policy_id: str) -> Dict[str, Any]:
        """Compute affected clients and workloads deterministically."""
        wp_stmt = select(WorkloadProtection).where(WorkloadProtection.policy_id == policy_id)
        protections = self.db.execute(wp_stmt).scalars().all()
        affected_workload_ids = [p.workload_id for p in protections]

        affected_client_ids = set()
        if affected_workload_ids:
            w_stmt = select(Workload).where(Workload.workload_id.in_(affected_workload_ids))
            workloads = self.db.execute(w_stmt).scalars().all()
            affected_client_ids = {w.client_id for w in workloads}

        return {
            "policy_id": policy_id,
            "affected_workload_count": len(affected_workload_ids),
            "affected_client_count": len(affected_client_ids),
            "workload_ids": affected_workload_ids,
            "client_ids": list(affected_client_ids)
        }

    def _record_audit(self, action: str, policy_id: str, user: str, details: str):
        audit = AuditLog(
            action=action,
            resource_type="policy",
            resource_id=policy_id,
            user_id=1,
            details=f"{details} (actor: {user})"
        )
        self.db.add(audit)
        self.db.commit()
