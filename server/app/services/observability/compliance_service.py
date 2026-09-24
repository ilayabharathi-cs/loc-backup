"""RetroVault V10 Compliance Evidence Engine.

Generates factual, tamper-verifiable evidence across 13 compliance domains without
making autonomous legal claims. Returns explicit evidence statuses:
EVIDENCE_AVAILABLE, EVIDENCE_MISSING, NOT_APPLICABLE, UNKNOWN.
"""

import uuid
import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session

from app.models.observability_v10_models import ComplianceEvidence
from app.models.backup_run import BackupRun
from app.models.recovery_point import RecoveryPoint
from app.models.restore_job import RestoreJob
from app.models.replication import ReplicationJob
from app.models.security_v8_models import IntegrityScan, DeletionGuard, SecurityIncident, ConfigurationDrift
from app.models.audit_log import AuditLog
from app.models.security_models import MfaSetting

logger = logging.getLogger(__name__)

COMPLIANCE_DOMAINS = [
    "backup_execution",
    "backup_success",
    "retention",
    "immutability",
    "restore_tests",
    "replication",
    "integrity_scans",
    "access_control",
    "mfa",
    "audit_events",
    "policy_changes",
    "deletion_approvals",
    "security_incidents"
]


class ComplianceEvidenceService:
    """Evaluates and records tamper-evident factual compliance records."""

    def __init__(self, db: Session):
        self.db = db

    def evaluate_all_domains(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[ComplianceEvidence]:
        """Evaluate evidence across all 13 compliance domains for the specified period."""
        end = end_time or datetime.now(timezone.utc)
        start = start_time or (end - timedelta(days=30))

        records = []
        for domain in COMPLIANCE_DOMAINS:
            rec = self.evaluate_domain(domain, start, end)
            records.append(rec)
        return records

    def evaluate_domain(
        self,
        domain: str,
        start_time: datetime,
        end_time: datetime
    ) -> ComplianceEvidence:
        """Evaluate factual evidence for a specific domain within a given time period."""
        if domain not in COMPLIANCE_DOMAINS:
            raise ValueError(f"Unknown compliance domain: {domain}")

        method_map = {
            "backup_execution": self._eval_backup_execution,
            "backup_success": self._eval_backup_success,
            "retention": self._eval_retention,
            "immutability": self._eval_immutability,
            "restore_tests": self._eval_restore_tests,
            "replication": self._eval_replication,
            "integrity_scans": self._eval_integrity_scans,
            "access_control": self._eval_access_control,
            "mfa": self._eval_mfa,
            "audit_events": self._eval_audit_events,
            "policy_changes": self._eval_policy_changes,
            "deletion_approvals": self._eval_deletion_approvals,
            "security_incidents": self._eval_security_incidents,
        }

        res = method_map[domain](start_time, end_time)

        # Compute cryptographic verification hash of the factual evidence payload
        payload_str = json.dumps(res["payload"], sort_keys=True)
        hash_input = f"{domain}:{res['status']}:{start_time.isoformat()}:{end_time.isoformat()}:{payload_str}"
        verification_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

        evidence_id = f"EVD-{domain.upper()}-{uuid.uuid4().hex[:8].upper()}"
        record = ComplianceEvidence(
            evidence_id=evidence_id,
            domain=domain,
            status=res["status"],
            resource_type=res.get("resource_type", "GLOBAL"),
            resource_id=res.get("resource_id", "SYSTEM"),
            period_start=start_time,
            period_end=end_time,
            evidence_summary=res["summary"],
            evidence_payload_json=payload_str,
            verification_hash=verification_hash,
            evaluated_at=datetime.now(timezone.utc)
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def _eval_backup_execution(self, start: datetime, end: datetime) -> Dict[str, Any]:
        count = self.db.scalar(
            select(func.count(BackupRun.id)).where(BackupRun.started_at >= start, BackupRun.started_at <= end)
        ) or 0
        if count > 0:
            return {
                "status": "EVIDENCE_AVAILABLE",
                "summary": f"{count} backup run executions logged during period.",
                "payload": {"backup_runs_executed": count}
            }
        return {
            "status": "EVIDENCE_MISSING",
            "summary": "No backup executions found during the evaluation period.",
            "payload": {"backup_runs_executed": 0}
        }

    def _eval_backup_success(self, start: datetime, end: datetime) -> Dict[str, Any]:
        total = self.db.scalar(
            select(func.count(BackupRun.id)).where(BackupRun.started_at >= start, BackupRun.started_at <= end)
        ) or 0
        succ = self.db.scalar(
            select(func.count(BackupRun.id)).where(
                BackupRun.started_at >= start,
                BackupRun.started_at <= end,
                func.upper(BackupRun.status).in_(["SUCCESS", "COMPLETED"])
            )
        ) or 0

        rate = (succ / total) * 100.0 if total > 0 else 0.0
        status = "EVIDENCE_AVAILABLE" if succ > 0 else "EVIDENCE_MISSING"
        return {
            "status": status,
            "summary": f"{succ}/{total} ({round(rate, 1)}%) backup runs succeeded during period.",
            "payload": {"total_runs": total, "successful_runs": succ, "success_rate_pct": round(rate, 2)}
        }

    def _eval_retention(self, start: datetime, end: datetime) -> Dict[str, Any]:
        from app.models.retention_policy import RetentionPolicy, RetentionEvaluation
        p_count = self.db.scalar(select(func.count(RetentionPolicy.id))) or 0
        e_count = self.db.scalar(
            select(func.count(RetentionEvaluation.id)).where(
                RetentionEvaluation.evaluated_at >= start,
                RetentionEvaluation.evaluated_at <= end
            )
        ) or 0
        status = "EVIDENCE_AVAILABLE" if p_count > 0 else "EVIDENCE_MISSING"
        return {
            "status": status,
            "summary": f"{p_count} retention policies active, {e_count} policy evaluations in period.",
            "payload": {"policies_configured": p_count, "evaluations_run": e_count}
        }

    def _eval_immutability(self, start: datetime, end: datetime) -> Dict[str, Any]:
        locked_points = self.db.scalar(
            select(func.count(RecoveryPoint.id)).where(RecoveryPoint.security_hold_until > datetime.now(timezone.utc))
        ) or 0
        return {
            "status": "EVIDENCE_AVAILABLE" if locked_points > 0 else "NOT_APPLICABLE",
            "summary": f"{locked_points} recovery points actively held under tamper-proof immutability lock.",
            "payload": {"immutable_recovery_points": locked_points}
        }

    def _eval_restore_tests(self, start: datetime, end: datetime) -> Dict[str, Any]:
        restores = self.db.scalar(
            select(func.count(RestoreJob.id)).where(RestoreJob.created_at >= start, RestoreJob.created_at <= end)
        ) or 0
        succ = self.db.scalar(
            select(func.count(RestoreJob.id)).where(
                RestoreJob.created_at >= start,
                RestoreJob.created_at <= end,
                RestoreJob.status == "COMPLETED"
            )
        ) or 0
        status = "EVIDENCE_AVAILABLE" if restores > 0 else "EVIDENCE_MISSING"
        return {
            "status": status,
            "summary": f"{succ}/{restores} restore/DR verification jobs executed successfully in period.",
            "payload": {"restores_tested": restores, "successful_restores": succ}
        }

    def _eval_replication(self, start: datetime, end: datetime) -> Dict[str, Any]:
        rep_jobs = self.db.scalar(
            select(func.count(ReplicationJob.id)).where(ReplicationJob.created_at >= start, ReplicationJob.created_at <= end)
        ) or 0
        return {
            "status": "EVIDENCE_AVAILABLE" if rep_jobs > 0 else "NOT_APPLICABLE",
            "summary": f"{rep_jobs} offsite replication sync operations logged in period.",
            "payload": {"replication_operations": rep_jobs}
        }

    def _eval_integrity_scans(self, start: datetime, end: datetime) -> Dict[str, Any]:
        scans = self.db.scalar(
            select(func.count(IntegrityScan.id)).where(IntegrityScan.created_at >= start, IntegrityScan.created_at <= end)
        ) or 0
        return {
            "status": "EVIDENCE_AVAILABLE" if scans > 0 else "EVIDENCE_MISSING",
            "summary": f"{scans} repository and CAS cryptographic integrity scans executed in period.",
            "payload": {"scans_executed": scans}
        }

    def _eval_access_control(self, start: datetime, end: datetime) -> Dict[str, Any]:
        from app.models.user import User
        users = list(self.db.scalars(select(User)).all())
        roles = {}
        for u in users:
            r = getattr(u, "role", "OPERATOR")
            roles[r] = roles.get(r, 0) + 1
        return {
            "status": "EVIDENCE_AVAILABLE",
            "summary": f"Role-based access controls active across {len(users)} users: {roles}",
            "payload": {"user_count": len(users), "roles_distribution": roles}
        }

    def _eval_mfa(self, start: datetime, end: datetime) -> Dict[str, Any]:
        mfa_enabled = self.db.scalar(
            select(func.count(MfaSetting.id)).where(MfaSetting.is_enabled == True)
        ) or 0
        return {
            "status": "EVIDENCE_AVAILABLE" if mfa_enabled > 0 else "EVIDENCE_MISSING",
            "summary": f"{mfa_enabled} administrator account(s) have TOTP MFA actively enforced.",
            "payload": {"mfa_active_users": mfa_enabled}
        }

    def _eval_audit_events(self, start: datetime, end: datetime) -> Dict[str, Any]:
        audits = self.db.scalar(
            select(func.count(AuditLog.id)).where(AuditLog.created_at >= start, AuditLog.created_at <= end)
        ) or 0
        return {
            "status": "EVIDENCE_AVAILABLE" if audits > 0 else "EVIDENCE_MISSING",
            "summary": f"{audits} auditable system actions logged in immutable audit trail.",
            "payload": {"audit_records": audits}
        }

    def _eval_policy_changes(self, start: datetime, end: datetime) -> Dict[str, Any]:
        drifts = self.db.scalar(
            select(func.count(ConfigurationDrift.id)).where(ConfigurationDrift.detected_at >= start, ConfigurationDrift.detected_at <= end)
        ) or 0
        return {
            "status": "EVIDENCE_AVAILABLE",
            "summary": f"{drifts} agent configuration drift events evaluated in period.",
            "payload": {"configuration_drifts_detected": drifts}
        }

    def _eval_deletion_approvals(self, start: datetime, end: datetime) -> Dict[str, Any]:
        guards = self.db.scalar(
            select(func.count(DeletionGuard.id)).where(DeletionGuard.created_at >= start, DeletionGuard.created_at <= end)
        ) or 0
        return {
            "status": "EVIDENCE_AVAILABLE" if guards > 0 else "NOT_APPLICABLE",
            "summary": f"{guards} two-man rule deletion guard requests tracked in period.",
            "payload": {"deletion_requests_tracked": guards}
        }

    def _eval_security_incidents(self, start: datetime, end: datetime) -> Dict[str, Any]:
        incidents = self.db.scalar(
            select(func.count(SecurityIncident.id)).where(SecurityIncident.created_at >= start, SecurityIncident.created_at <= end)
        ) or 0
        return {
            "status": "EVIDENCE_AVAILABLE",
            "summary": f"{incidents} security incidents evaluated in period.",
            "payload": {"security_incidents": incidents}
        }
