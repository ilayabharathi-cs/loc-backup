"""RetroVault V11: Safe Remediation Service with Approval Gates."""

import json
import uuid
import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.workload_v11_models import RemediationAction, Workload
from app.models.audit_log import AuditLog


ALLOWED_REMEDIATIONS = [
    "RETRY_BACKUP",
    "RERUN_VERIFICATION",
    "REENABLE_PROTECTION",
    "MOVE_REPOSITORY",
    "TRIGGER_REPLICATION",
    "ROTATE_CREDENTIALS",
    "START_RECOVERY_VERIFICATION"
]

DESTRUCTIVE_PROHIBITED = [
    "DELETE_RECOVERY_POINT",
    "PURGE_CAS_OBJECTS",
    "DISABLE_IMMUTABILITY",
    "DISABLE_RANSOMWARE_PROTECTION",
    "BYPASS_DELETION_GUARD"
]


class RemediationService:
    """Manages safe remediation workflows with explicit approval gates."""

    def __init__(self, db: Session):
        self.db = db

    def propose_remediation(
        self,
        action_type: str,
        target_resource_type: str,
        target_resource_id: str,
        proposed_by: str = "SYSTEM",
        requires_dual_approval: bool = False
    ) -> RemediationAction:
        """Propose a remediation action. Strictly rejects any prohibited destructive operations."""
        if action_type in DESTRUCTIVE_PROHIBITED:
            raise PermissionError(
                f"Security Invariant Violation: Autonomous destructive action '{action_type}' is strictly prohibited."
            )

        if action_type not in ALLOWED_REMEDIATIONS:
            raise ValueError(f"Unknown remediation action type '{action_type}'. Allowed: {ALLOWED_REMEDIATIONS}")

        rem_id = f"rem-{uuid.uuid4().hex[:12]}"
        now = datetime.datetime.now(datetime.timezone.utc)

        action = RemediationAction(
            remediation_id=rem_id,
            action_type=action_type,
            target_resource_type=target_resource_type,
            target_resource_id=target_resource_id,
            requires_dual_approval=requires_dual_approval,
            first_approver=proposed_by if proposed_by != "SYSTEM" else None,
            status="PENDING_APPROVAL",
            created_at=now
        )
        self.db.add(action)

        # Audit proposal
        audit = AuditLog(
            action="REMEDIATION_PROPOSED",
            resource_type=target_resource_type,
            resource_id=target_resource_id,
            user_id=1,
            details=f"Remediation {action_type} proposed by {proposed_by} (dual approval required: {requires_dual_approval})"
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(action)
        return action

    def approve_remediation(self, remediation_id: str, approver: str) -> RemediationAction:
        """Approve a proposed remediation. Validates dual-approval if required."""
        stmt = select(RemediationAction).where(RemediationAction.remediation_id == remediation_id)
        action = self.db.execute(stmt).scalars().first()
        if not action:
            raise ValueError(f"Remediation '{remediation_id}' not found")

        if action.status not in ["PENDING_APPROVAL"]:
            raise ValueError(f"Cannot approve remediation in state '{action.status}'")

        if action.requires_dual_approval:
            if not action.first_approver:
                action.first_approver = approver
            elif action.first_approver == approver:
                raise PermissionError("Dual approval requirement: Second approver must be different from first approver")
            else:
                action.second_approver = approver
                action.status = "APPROVED"
        else:
            action.first_approver = approver
            action.status = "APPROVED"

        audit = AuditLog(
            action="REMEDIATION_APPROVED",
            resource_type=action.target_resource_type,
            resource_id=action.target_resource_id,
            user_id=1,
            details=f"Remediation {action.action_type} approved by {approver}"
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(action)
        return action

    def execute_remediation(self, remediation_id: str, executor: str = "SYSTEM") -> Dict[str, Any]:
        """Execute an approved remediation safely."""
        stmt = select(RemediationAction).where(RemediationAction.remediation_id == remediation_id)
        action = self.db.execute(stmt).scalars().first()
        if not action:
            return {"success": False, "error": f"Remediation '{remediation_id}' not found"}

        if action.status != "APPROVED":
            return {"success": False, "error": f"Remediation must be in 'APPROVED' state, currently '{action.status}'"}

        action.status = "EXECUTING"
        self.db.commit()

        now = datetime.datetime.now(datetime.timezone.utc)
        result_payload: Dict[str, Any] = {"status": "SUCCESS"}

        try:
            if action.action_type == "REENABLE_PROTECTION":
                w_stmt = select(Workload).where(Workload.workload_id == action.target_resource_id)
                w = self.db.execute(w_stmt).scalars().first()
                if w:
                    w.protection_state = "PROTECTED"
                    result_payload["message"] = f"Workload {w.workload_id} protection resumed"

            elif action.action_type == "RETRY_BACKUP":
                result_payload["message"] = f"Triggered backup retry for {action.target_resource_id}"

            elif action.action_type in ["RERUN_VERIFICATION", "START_RECOVERY_VERIFICATION"]:
                result_payload["message"] = f"Scheduled verification rerun for {action.target_resource_id}"

            action.status = "COMPLETED"
            action.executed_at = now
            action.execution_result_json = json.dumps(result_payload)

            audit = AuditLog(
                action="REMEDIATION_EXECUTED",
                resource_type=action.target_resource_type,
                resource_id=action.target_resource_id,
                user_id=1,
                details=f"Remediation {action.action_type} executed by {executor}"
            )
            self.db.add(audit)
            self.db.commit()
            return {"success": True, "result": result_payload}

        except Exception as e:
            action.status = "FAILED"
            action.execution_result_json = json.dumps({"error": str(e)})
            self.db.commit()
            return {"success": False, "error": str(e)}
