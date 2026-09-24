"""Alerting and Notification Engine for RetroVault V7."""

import datetime
import json
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from app.models.alert import AlertRule, Alert, NotificationChannel, NotificationDelivery
from app.models.client import Client
from app.models.storage_repository import StorageRepository
from app.models.storage_object import StorageObject
from app.models.backup_run import BackupRun
from app.models.replication import ReplicationJob


class AlertEngine:
    """Manages alert generation, rule evaluation, deduplication, and notification dispatch."""

    def __init__(self, db: Session):
        self.db = db

    def trigger_alert(
        self,
        alert_type: str,
        title: str,
        message: str,
        severity: str = "WARNING",
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        rule_id: Optional[int] = None
    ) -> Alert:
        """Trigger an alert with deduplication against existing active alerts."""
        now = datetime.datetime.now(datetime.timezone.utc)

        # Check existing active alert for same type and resource
        existing = self.db.query(Alert).filter(
            Alert.alert_type == alert_type,
            Alert.resource_id == str(resource_id) if resource_id else None,
            Alert.status == "ACTIVE"
        ).first()

        if existing:
            # Update message and timestamp
            existing.message = message
            existing.created_at = now
            self.db.commit()
            self.db.refresh(existing)
            return existing

        alert = Alert(
            rule_id=rule_id,
            alert_type=alert_type,
            severity=severity.upper(),
            title=title,
            message=message,
            status="ACTIVE",
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            created_at=now
        )
        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)

        # Dispatch notifications
        self._dispatch_notifications(alert)
        return alert

    def acknowledge_alert(self, alert_id: int, username: str) -> Alert:
        """Acknowledge an active alert."""
        alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            raise ValueError(f"Alert #{alert_id} not found")
        alert.status = "ACKNOWLEDGED"
        alert.acknowledged_by = username
        alert.acknowledged_at = datetime.datetime.now(datetime.timezone.utc)
        self.db.commit()
        self.db.refresh(alert)
        return alert

    def resolve_alert(self, alert_id: int) -> Alert:
        """Resolve an active or acknowledged alert."""
        alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            raise ValueError(f"Alert #{alert_id} not found")
        alert.status = "RESOLVED"
        alert.resolved_at = datetime.datetime.now(datetime.timezone.utc)
        self.db.commit()
        self.db.refresh(alert)
        return alert

    def evaluate_rules(self) -> List[Alert]:
        """Evaluate system state against active alert rules."""
        generated: List[Alert] = []
        rules = self.db.query(AlertRule).filter(AlertRule.is_enabled == True).all()

        for rule in rules:
            if rule.rule_type == "AGENT_OFFLINE":
                # Check for clients that missed heartbeat beyond threshold seconds
                threshold = int(rule.threshold_value or 300)
                cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=threshold)
                offline_clients = self.db.query(Client).filter(
                    Client.status.in_(["active", "online"]),
                    Client.last_seen < cutoff
                ).all()
                for c in offline_clients:
                    a = self.trigger_alert(
                        alert_type="AGENT_OFFLINE",
                        title=f"Agent Offline: {c.hostname}",
                        message=f"Client {c.client_id} ({c.hostname}) has not reported heartbeat since {c.last_seen}",
                        severity=rule.severity,
                        resource_type="client",
                        resource_id=c.client_id,
                        rule_id=rule.id
                    )
                    generated.append(a)

            elif rule.rule_type == "REPOSITORY_OFFLINE":
                offline_repos = self.db.query(StorageRepository).filter(
                    StorageRepository.status == "OFFLINE"
                ).all()
                for r in offline_repos:
                    a = self.trigger_alert(
                        alert_type="REPOSITORY_OFFLINE",
                        title=f"Repository Offline: {r.name}",
                        message=f"Storage repository '{r.name}' is unreachable or marked OFFLINE.",
                        severity="CRITICAL",
                        resource_type="repository",
                        resource_id=str(r.id),
                        rule_id=rule.id
                    )
                    generated.append(a)

            elif rule.rule_type == "CORRUPTED_OBJECT":
                corrupted = self.db.query(StorageObject).filter(StorageObject.state == "CORRUPTED").all()
                if corrupted:
                    a = self.trigger_alert(
                        alert_type="CORRUPTED_OBJECT",
                        title=f"Storage Integrity Bit-Rot Detected ({len(corrupted)} objects)",
                        message=f"Discovered {len(corrupted)} corrupted CAS storage objects in repository.",
                        severity="CRITICAL",
                        resource_type="storage",
                        resource_id="integrity",
                        rule_id=rule.id
                    )
                    generated.append(a)

        return generated

    def _dispatch_notifications(self, alert: Alert):
        """Dispatch notifications to enabled channels."""
        channels = self.db.query(NotificationChannel).filter(NotificationChannel.is_enabled == True).all()
        now = datetime.datetime.now(datetime.timezone.utc)

        for ch in channels:
            # Check cooldown
            if ch.last_sent_at and (now - ch.last_sent_at).total_seconds() < ch.cooldown_seconds:
                continue

            payload = json.dumps({
                "alert_id": alert.id,
                "type": alert.alert_type,
                "severity": alert.severity,
                "title": alert.title,
                "message": alert.message,
                "timestamp": now.isoformat()
            })

            # Record simulated delivery
            delivery = NotificationDelivery(
                channel_id=ch.id,
                alert_id=alert.id,
                status="SENT",
                payload=payload,
                sent_at=now
            )
            self.db.add(delivery)
            ch.last_sent_at = now

        self.db.commit()
