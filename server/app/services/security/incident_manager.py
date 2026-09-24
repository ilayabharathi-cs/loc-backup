"""Security Incident Manager for RetroVault V8.

Implements the complete 10-state security incident lifecycle:
DETECTED -> CONFIRMED -> TRIAGED -> CONTAINED -> REMEDIATING -> VERIFYING -> RESOLVED -> CLOSED
(with support for FALSE_POSITIVE and ESCALATED).
"""

import datetime
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.security_v8_models import SecurityIncident, SecurityEvent
from app.models.recovery_point import RecoveryPoint

logger = logging.getLogger(__name__)


class IncidentManager:
    """Manages the full lifecycle of ransomware and security incidents."""

    ALLOWED_STATUSES = [
        "DETECTED", "CONFIRMED", "TRIAGED", "CONTAINED",
        "REMEDIATING", "VERIFYING", "RESOLVED", "CLOSED",
        "FALSE_POSITIVE", "ESCALATED"
    ]

    def __init__(self, db: Session):
        self.db = db

    def create_incident(
        self,
        title: str,
        severity: str = "HIGH",
        client_id: Optional[int] = None,
        candidate_recovery_point_id: Optional[int] = None,
        containment_notes: Optional[str] = None
    ) -> SecurityIncident:
        """Creates a new incident in DETECTED state."""
        timestamp_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
        inc_num = f"INC-{timestamp_str}"

        incident = SecurityIncident(
            incident_number=inc_num,
            title=title,
            severity=severity,
            status="DETECTED",
            client_id=client_id,
            candidate_recovery_point_id=candidate_recovery_point_id,
            containment_notes=containment_notes
        )
        self.db.add(incident)
        self.db.commit()
        self.db.refresh(incident)
        return incident

    def transition_status(
        self,
        incident_id: int,
        new_status: str,
        operator_username: str = "admin",
        notes: Optional[str] = None,
        candidate_rp_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Transitions an incident through the lifecycle."""
        inc = self.db.query(SecurityIncident).filter(SecurityIncident.id == incident_id).first()
        if not inc:
            return {"error": f"Incident {incident_id} not found", "success": False}

        new_status = new_status.upper()
        if new_status not in self.ALLOWED_STATUSES:
            return {"error": f"Invalid status: {new_status}. Allowed: {self.ALLOWED_STATUSES}", "success": False}

        old_status = inc.status
        inc.status = new_status
        inc.updated_at = datetime.datetime.now(datetime.timezone.utc)

        if notes:
            existing = inc.containment_notes or ""
            inc.containment_notes = f"{existing}\n[{new_status} by {operator_username}]: {notes}".strip()

        if candidate_rp_id:
            inc.candidate_recovery_point_id = candidate_rp_id

        if new_status == "CLOSED":
            inc.closed_at = datetime.datetime.now(datetime.timezone.utc)
            inc.closed_by = operator_username

        self.db.commit()
        self.db.refresh(inc)

        return {
            "incident_id": inc.id,
            "incident_number": inc.incident_number,
            "previous_status": old_status,
            "current_status": inc.status,
            "candidate_recovery_point_id": inc.candidate_recovery_point_id,
            "success": True
        }
