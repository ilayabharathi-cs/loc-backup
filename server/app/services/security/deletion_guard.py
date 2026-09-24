"""Mass-Deletion Guard service for RetroVault V8.

Intercepts destructive operations, calculates risk scores, requires dual-authorization/MFA,
and queues requests for administrator review.
"""

import datetime
import json
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.recovery_point import RecoveryPoint
from app.models.backup_policy import BackupPolicy
from app.models.security_v8_models import DeletionGuard, SecurityEvent, SecurityProfile

logger = logging.getLogger(__name__)


class DeletionGuardService:
    """Safeguards backup data and policies against malicious or accidental bulk deletion."""

    def __init__(self, db: Session):
        self.db = db

    def evaluate_request(
        self,
        request_type: str,  # DELETE_RECOVERY_POINTS, PURGE_REPOSITORY, DELETE_POLICY, BULK_EXPIRE
        target_resource_type: str,
        target_resource_id: str,
        payload: Dict[str, Any],
        requester_username: str,
        requester_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Calculates risk score and either allows execution or blocks until MFA/Admin approval."""
        profile = self.db.query(SecurityProfile).filter(SecurityProfile.is_default == True).first()
        max_deletion_count = profile.max_deletion_count if profile else 5
        max_deletion_pct = profile.max_deletion_pct if profile else 10.0
        require_mfa = profile.require_mfa_for_deletion if profile else True

        risk_score = 0
        risk_factors: List[str] = []

        # Analyze target resource
        if request_type == "DELETE_RECOVERY_POINTS":
            point_ids = payload.get("recovery_point_ids", [])
            count = len(point_ids)
            total_active = self.db.query(RecoveryPoint).filter(RecoveryPoint.retention_status == "active").count() or 1
            pct = (count / total_active) * 100.0

            if count > max_deletion_count:
                risk_score += 40
                risk_factors.append(f"Count ({count}) exceeds maximum threshold ({max_deletion_count})")
            if pct > max_deletion_pct:
                risk_score += 35
                risk_factors.append(f"Percentage ({pct:.1f}%) exceeds maximum safe threshold ({max_deletion_pct}%)")

            # Check if any requested recovery point is under SECURITY_HOLD or PROTECTED
            held_points = (
                self.db.query(RecoveryPoint)
                .filter(
                    RecoveryPoint.id.in_(point_ids),
                    RecoveryPoint.protection_state.in_(["PROTECTED", "RETENTION_LOCKED", "SECURITY_HOLD", "QUARANTINED"])
                )
                .all()
            )
            if held_points:
                risk_score += 50
                risk_factors.append(
                    f"{len(held_points)} recovery point(s) are actively protected or under SECURITY_HOLD: "
                    f"{[p.id for p in held_points]}"
                )

        elif request_type == "PURGE_REPOSITORY":
            risk_score += 85
            risk_factors.append("Repository purge is a high-impact destructive action")

        elif request_type == "DELETE_POLICY":
            risk_score += 45
            risk_factors.append("Backup policy deletion affects scheduled client backups")

        else:
            risk_score += 25
            risk_factors.append(f"Unclassified deletion operation: {request_type}")

        risk_score = min(risk_score, 100)
        requires_approval = risk_score >= 50 or require_mfa

        # Create DeletionGuard pending record
        expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24)
        guard_entry = DeletionGuard(
            request_type=request_type,
            requester_id=requester_id,
            requester_username=requester_username,
            target_resource_type=target_resource_type,
            target_resource_id=str(target_resource_id),
            payload_json=json.dumps(payload),
            status="PENDING" if requires_approval else "APPROVED",
            risk_score=risk_score,
            expires_at=expires_at
        )
        self.db.add(guard_entry)

        # Emit security event if risk is significant
        if risk_score >= 50:
            event = SecurityEvent(
                event_type="UNUSUAL_DELETION",
                severity="HIGH" if risk_score >= 70 else "MEDIUM",
                score=risk_score,
                description=f"Mass-Deletion Guard intercepted {request_type} by {requester_username}. Risk: {risk_score}/100.",
                evidence_json=json.dumps({"risk_factors": risk_factors, "payload": payload}),
                status="OPEN"
            )
            self.db.add(event)

        self.db.commit()

        return {
            "guard_id": guard_entry.id,
            "status": guard_entry.status,
            "risk_score": risk_score,
            "requires_approval": requires_approval,
            "risk_factors": risk_factors,
            "expires_at": expires_at.isoformat()
        }

    def approve_request(
        self,
        guard_id: int,
        approver_username: str,
        mfa_verified: bool = False
    ) -> Dict[str, Any]:
        """Approves a pending deletion guard request."""
        guard = self.db.query(DeletionGuard).filter(DeletionGuard.id == guard_id).first()
        if not guard:
            return {"error": f"Guard request {guard_id} not found", "success": False}

        if guard.status != "PENDING":
            return {"error": f"Guard request is already {guard.status}", "success": False}

        profile = self.db.query(SecurityProfile).filter(SecurityProfile.is_default == True).first()
        require_mfa = profile.require_mfa_for_deletion if profile else True
        if require_mfa and not mfa_verified:
            return {"error": "MFA verification is required to approve this deletion request", "success": False}

        # Prevent requester from approving own high-risk request (dual authorization)
        if guard.requester_username.lower() == approver_username.lower() and guard.risk_score >= 60:
            return {"error": "Dual-authorization required: Approver cannot be the same as requester for high-risk deletions", "success": False}

        guard.status = "APPROVED"
        guard.approved_by = approver_username
        guard.approved_at = datetime.datetime.now(datetime.timezone.utc)
        self.db.commit()

        return {
            "guard_id": guard.id,
            "status": "APPROVED",
            "approved_by": approver_username,
            "payload": json.loads(guard.payload_json)
        }

    def reject_request(self, guard_id: int, rejector_username: str, reason: str = "") -> Dict[str, Any]:
        """Rejects a pending deletion guard request."""
        guard = self.db.query(DeletionGuard).filter(DeletionGuard.id == guard_id).first()
        if not guard:
            return {"error": f"Guard request {guard_id} not found", "success": False}

        guard.status = "REJECTED"
        guard.approved_by = f"REJECTED by {rejector_username}: {reason}"
        self.db.commit()
        return {"guard_id": guard.id, "status": "REJECTED"}
