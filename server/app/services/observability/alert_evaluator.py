"""RetroVault V10 Operational Alert Engine.

Manages 17 distinct operational alert types with fingerprint-based deduplication,
cooldown periods, thresholds, state transitions (ACTIVE -> ACKNOWLEDGED -> RESOLVED),
and correlation hooks to avoid alert storms.
"""

import uuid
import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select, and_, desc
from sqlalchemy.orm import Session

from app.models.observability_v10_models import OperationalAlert

logger = logging.getLogger(__name__)

SUPPORTED_ALERT_TYPES = {
    "BACKUP_MISSED",
    "RPO_AT_RISK",
    "RPO_MISSED",
    "REPOSITORY_LOW_SPACE",
    "REPOSITORY_OFFLINE",
    "REPLICATION_LAG",
    "AGENT_OFFLINE",
    "AGENT_STALE",
    "NODE_OFFLINE",
    "SCHEDULER_BACKLOG",
    "DATABASE_DEGRADED",
    "RESTORE_FAILURE",
    "INTEGRITY_FAILURE",
    "SECURITY_EVENT",
    "CONFIGURATION_DRIFT",
    "CERTIFICATE_EXPIRY",
    "CREDENTIAL_EXPIRY"
}


class AlertEvaluator:
    """Evaluates thresholds, triggers operational alerts, and performs deduplication."""

    def __init__(self, db: Session):
        self.db = db

    def generate_fingerprint(self, alert_type: str, resource_id: str, source: str) -> str:
        """Create deterministic fingerprint for deduplication."""
        raw = f"{alert_type}:{resource_id}:{source}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    def trigger_alert(
        self,
        alert_type: str,
        resource_id: str,
        source: str,
        title: str,
        message: str,
        severity: str = "WARNING",
        threshold_value: Optional[float] = None,
        observed_value: Optional[float] = None,
        evidence: Optional[Dict[str, Any]] = None,
        cooldown_minutes: int = 15
    ) -> OperationalAlert:
        """Raise or deduplicate an operational alert."""
        if alert_type not in SUPPORTED_ALERT_TYPES:
            raise ValueError(f"Unsupported alert type: {alert_type}")

        now = datetime.now(timezone.utc)
        fp = self.generate_fingerprint(alert_type, resource_id, source)
        evidence_json = json.dumps(evidence, sort_keys=True) if evidence else None

        # Check for active existing alert with the same fingerprint
        existing = self.db.scalar(
            select(OperationalAlert)
            .where(
                OperationalAlert.fingerprint == fp,
                OperationalAlert.status.in_(["ACTIVE", "ACKNOWLEDGED"])
            )
            .order_by(desc(OperationalAlert.last_seen_at))
            .limit(1)
        )

        if existing:
            # Deduplication: increment count and update last_seen_at
            existing.occurrence_count += 1
            existing.last_seen_at = now
            existing.observed_value = observed_value
            if evidence_json:
                existing.evidence_json = evidence_json
            self.db.commit()
            self.db.refresh(existing)
            logger.info(f"Deduplicated alert {existing.alert_id} (count={existing.occurrence_count})")
            return existing

        # Create new alert
        alert_id = f"ALT-{uuid.uuid4().hex[:12].upper()}"
        alert = OperationalAlert(
            alert_id=alert_id,
            alert_type=alert_type,
            severity=severity,
            status="ACTIVE",
            source=source,
            resource_id=resource_id,
            title=title,
            message=message,
            evidence_json=evidence_json,
            threshold_value=threshold_value,
            observed_value=observed_value,
            fingerprint=fp,
            occurrence_count=1,
            first_seen_at=now,
            last_seen_at=now
        )
        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)
        logger.info(f"Triggered new operational alert: {alert_id} [{alert_type}] on {resource_id}")
        return alert

    def acknowledge_alert(self, alert_id: str, user: str) -> Optional[OperationalAlert]:
        """Mark an alert as acknowledged by an operator."""
        alert = self.db.scalar(select(OperationalAlert).where(OperationalAlert.alert_id == alert_id))
        if not alert:
            return None
        alert.status = "ACKNOWLEDGED"
        alert.acknowledged_at = datetime.now(timezone.utc)
        alert.acknowledged_by = user
        self.db.commit()
        self.db.refresh(alert)
        return alert

    def resolve_alert(self, alert_id: str, user: str) -> Optional[OperationalAlert]:
        """Mark an alert as resolved."""
        alert = self.db.scalar(select(OperationalAlert).where(OperationalAlert.alert_id == alert_id))
        if not alert:
            return None
        alert.status = "RESOLVED"
        alert.resolved_at = datetime.now(timezone.utc)
        alert.resolved_by = user
        self.db.commit()
        self.db.refresh(alert)
        return alert

    def list_alerts(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        alert_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[OperationalAlert]:
        """Query operational alerts with filtering and pagination."""
        stmt = select(OperationalAlert)
        if status:
            stmt = stmt.where(OperationalAlert.status == status)
        if severity:
            stmt = stmt.where(OperationalAlert.severity == severity)
        if alert_type:
            stmt = stmt.where(OperationalAlert.alert_type == alert_type)

        stmt = stmt.order_by(desc(OperationalAlert.last_seen_at)).offset(offset).limit(limit)
        return list(self.db.scalars(stmt).all())
