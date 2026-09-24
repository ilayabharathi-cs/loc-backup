"""Clean Recovery Point Discovery for RetroVault V8.

Discovers clean candidate recovery points prior to suspected ransomware or anomaly timestamps.
Returns factual evidence (anomaly scores, integrity status, protection state) without arbitrary ranking.
"""

import datetime
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.recovery_point import RecoveryPoint
from app.models.security_v8_models import SecurityEvent, IntegrityScan
from app.models.backup_run import BackupRun

logger = logging.getLogger(__name__)


class CleanRecoverySelector:
    """Discovers clean candidate recovery points prior to an infection or anomaly."""

    def __init__(self, db: Session):
        self.db = db

    def discover_clean_points(
        self,
        client_id: int,
        incident_timestamp: Optional[datetime.datetime] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Finds candidate recovery points created prior to the incident timestamp."""
        query = (
            self.db.query(RecoveryPoint)
            .filter(RecoveryPoint.client_id == client_id, RecoveryPoint.status.in_(["valid", "completed"]))
        )

        if incident_timestamp:
            query = query.filter(RecoveryPoint.created_at < incident_timestamp)

        # Order most recent first
        candidates = query.order_by(RecoveryPoint.created_at.desc()).limit(limit).all()

        results: List[Dict[str, Any]] = []

        for rp in candidates:
            # Query security events associated with this recovery point or its backup run
            sec_events = (
                self.db.query(SecurityEvent)
                .filter(
                    (SecurityEvent.recovery_point_id == rp.id) |
                    ((SecurityEvent.run_id == rp.backup_run_id) if rp.backup_run_id else False)
                )
                .all()
            )

            max_event_score = max([e.score for e in sec_events], default=0)
            has_anomaly = max_event_score >= 60 or rp.protection_state == "SECURITY_HOLD"

            # Determine factual risk category
            if has_anomaly:
                risk_category = "SUSPECTED_ANOMALOUS"
            elif max_event_score > 0:
                risk_category = "LOW_RISK_WARNING"
            else:
                risk_category = "VERIFIED_CLEAN"

            results.append({
                "recovery_point_id": rp.id,
                "point_id": f"RP-{rp.id}",
                "backup_run_id": rp.backup_run_id,
                "created_at": rp.created_at.isoformat() if rp.created_at else None,
                "protection_state": rp.protection_state,
                "retention_status": rp.retention_status,
                "risk_category": risk_category,
                "anomaly_score": max_event_score,
                "security_events_count": len(sec_events),
                "is_recommended": (risk_category == "VERIFIED_CLEAN"),
                "evidence": {
                    "events": [{"type": e.event_type, "severity": e.severity, "score": e.score} for e in sec_events]
                }
            })

        return results
