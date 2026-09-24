"""SLA and RPO Compliance Monitor for RetroVault V7."""

import datetime
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from app.models.client import Client
from app.models.backup_policy import BackupPolicy
from app.models.recovery_point import RecoveryPoint
from app.models.replication import ReplicationJob


def _to_naive_utc(dt: Optional[datetime.datetime]) -> Optional[datetime.datetime]:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    return dt


class SlaMonitor:
    """Monitors observed recovery point ages against policy targets to detect RPO breaches."""

    def __init__(self, db: Session):
        self.db = db

    def evaluate_rpo_compliance(self) -> Dict[str, Any]:
        now = datetime.datetime.utcnow()
        clients = self.db.query(Client).all()
        policies = self.db.query(BackupPolicy).all()
        default_policy = next((p for p in policies if p.is_active), None)
        target_rpo_sec = default_policy.rpo_target_seconds if default_policy else 120

        client_reports: List[Dict[str, Any]] = []
        overall_compliant = True

        for client in clients:
            # Latest Recovery Point for this client
            latest_rp = self.db.query(RecoveryPoint).filter(
                RecoveryPoint.client_id == client.id,
                RecoveryPoint.status.in_(["valid", "completed"])
            ).order_by(RecoveryPoint.created_at.desc()).first()

            # Latest full backup
            latest_full = self.db.query(RecoveryPoint).filter(
                RecoveryPoint.client_id == client.id,
                RecoveryPoint.backup_type == "full",
                RecoveryPoint.status.in_(["valid", "completed"])
            ).order_by(RecoveryPoint.created_at.desc()).first()

            # Latest incremental backup
            latest_inc = self.db.query(RecoveryPoint).filter(
                RecoveryPoint.client_id == client.id,
                RecoveryPoint.backup_type == "incremental",
                RecoveryPoint.status.in_(["valid", "completed"])
            ).order_by(RecoveryPoint.created_at.desc()).first()

            backup_age_sec = (now - _to_naive_utc(latest_rp.created_at)).total_seconds() if (latest_rp and latest_rp.created_at) else None
            heartbeat_age_sec = (now - _to_naive_utc(client.last_seen)).total_seconds() if client.last_seen else None

            is_breached = False
            if backup_age_sec is None or backup_age_sec > target_rpo_sec:
                is_breached = True
                overall_compliant = False

            client_reports.append({
                "client_id": client.client_id,
                "hostname": client.hostname,
                "rpo_target_seconds": target_rpo_sec,
                "observed_backup_age_seconds": int(backup_age_sec) if backup_age_sec is not None else None,
                "status": "RPO BREACH" if is_breached else "RPO COMPLIANT",
                "last_backup_time": latest_rp.created_at.isoformat() if (latest_rp and latest_rp.created_at) else None,
                "last_full_time": latest_full.created_at.isoformat() if (latest_full and latest_full.created_at) else None,
                "last_incremental_time": latest_inc.created_at.isoformat() if (latest_inc and latest_inc.created_at) else None,
                "heartbeat_age_seconds": int(heartbeat_age_sec) if heartbeat_age_sec is not None else None
            })

        # Latest replication job age
        latest_repl = self.db.query(ReplicationJob).filter(
            ReplicationJob.status == "COMPLETED"
        ).order_by(ReplicationJob.completed_at.desc()).first()
        repl_age_sec = (now - _to_naive_utc(latest_repl.completed_at)).total_seconds() if (latest_repl and latest_repl.completed_at) else None

        return {
            "status": "RPO COMPLIANT" if overall_compliant and clients else "RPO BREACH",
            "target_rpo_seconds": target_rpo_sec,
            "clients_count": len(clients),
            "compliant_clients": sum(1 for c in client_reports if c["status"] == "RPO COMPLIANT"),
            "breached_clients": sum(1 for c in client_reports if c["status"] == "RPO BREACH"),
            "latest_replication_age_seconds": int(repl_age_sec) if repl_age_sec is not None else None,
            "clients": client_reports
        }
