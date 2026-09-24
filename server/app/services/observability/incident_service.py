"""RetroVault V10 Incident Correlation & Root-Cause Evidence Engine.

Correlates alert storms (e.g. 100 backup failures from 1 offline repository) into
a single OperationalIncident with affected resources, child alerts, and timeline tracking.
"""

import uuid
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select, and_, desc
from sqlalchemy.orm import Session

from app.models.observability_v10_models import OperationalAlert, OperationalIncident

logger = logging.getLogger(__name__)

SUPPORTED_INCIDENT_STATUSES = {
    "DETECTED",
    "ACKNOWLEDGED",
    "INVESTIGATING",
    "MITIGATING",
    "MONITORING",
    "RESOLVED",
    "CLOSED"
}


class IncidentService:
    """Manages operational incidents, root-cause correlation, and resolution lifecycles."""

    def __init__(self, db: Session):
        self.db = db

    def correlate_alerts(
        self,
        root_event: str,
        title: str,
        alert_ids: List[str],
        affected_resources: List[str],
        severity: str = "HIGH",
        relationship_type: str = "CAUSAL",
        evidence: Optional[Dict[str, Any]] = None
    ) -> OperationalIncident:
        """Create or update a correlated operational incident grouping multiple child alerts."""
        now = datetime.now(timezone.utc)
        incident_id = f"INC-{uuid.uuid4().hex[:10].upper()}"

        timeline = [{
            "timestamp": now.isoformat(),
            "event": "INCIDENT_DETECTED",
            "message": f"Correlated {len(alert_ids)} alerts into incident under root event: {root_event}"
        }]

        incident = OperationalIncident(
            incident_id=incident_id,
            title=title,
            status="DETECTED",
            severity=severity,
            root_event=root_event,
            relationship_type=relationship_type,
            affected_resources_json=json.dumps(affected_resources),
            child_alerts_json=json.dumps(alert_ids),
            timeline_json=json.dumps(timeline),
            evidence_json=json.dumps(evidence) if evidence else None,
            mitigation_steps=None,
            created_at=now,
            updated_at=now
        )
        self.db.add(incident)

        # Associate child alerts with this incident
        if alert_ids:
            alerts = list(self.db.scalars(
                select(OperationalAlert).where(OperationalAlert.alert_id.in_(alert_ids))
            ).all())
            for a in alerts:
                a.incident_id = incident_id

        self.db.commit()
        self.db.refresh(incident)
        logger.info(f"Created correlated incident {incident_id} ({len(alert_ids)} child alerts)")
        return incident

    def update_incident_status(
        self,
        incident_id: str,
        new_status: str,
        user: str,
        note: Optional[str] = None
    ) -> Optional[OperationalIncident]:
        """Progress incident through lifecycle (INVESTIGATING, MITIGATING, RESOLVED, etc.)."""
        if new_status not in SUPPORTED_INCIDENT_STATUSES:
            raise ValueError(f"Invalid incident status: {new_status}")

        incident = self.db.scalar(
            select(OperationalIncident).where(OperationalIncident.incident_id == incident_id)
        )
        if not incident:
            return None

        now = datetime.now(timezone.utc)
        timeline = json.loads(incident.timeline_json or "[]")
        timeline.append({
            "timestamp": now.isoformat(),
            "event": f"STATUS_CHANGE_TO_{new_status}",
            "user": user,
            "note": note or f"Status changed to {new_status}"
        })

        incident.status = new_status
        incident.updated_at = now
        incident.timeline_json = json.dumps(timeline)

        if new_status in ("RESOLVED", "CLOSED"):
            incident.resolved_at = now
            incident.resolved_by = user

            # Auto-resolve linked active alerts
            child_alert_ids = json.loads(incident.child_alerts_json or "[]")
            if child_alert_ids:
                alerts = list(self.db.scalars(
                    select(OperationalAlert).where(OperationalAlert.alert_id.in_(child_alert_ids))
                ).all())
                for a in alerts:
                    if a.status in ("ACTIVE", "ACKNOWLEDGED"):
                        a.status = "RESOLVED"
                        a.resolved_at = now
                        a.resolved_by = user

        self.db.commit()
        self.db.refresh(incident)
        return incident

    def list_incidents(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[OperationalIncident]:
        """Query operational incidents with filtering and pagination."""
        stmt = select(OperationalIncident)
        if status:
            stmt = stmt.where(OperationalIncident.status == status)
        if severity:
            stmt = stmt.where(OperationalIncident.severity == severity)

        stmt = stmt.order_by(desc(OperationalIncident.created_at)).offset(offset).limit(limit)
        return list(self.db.scalars(stmt).all())
