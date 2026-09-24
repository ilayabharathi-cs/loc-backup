"""RetroVault V10 Enterprise Report Generator Subsystem.

Compiles factual evidence into 11 auditable report types and renders them
as JSON, CSV, or PDF artifacts with verifiable SHA-256 integrity checksums.
"""

import os
import csv
import json
import uuid
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from io import StringIO
from typing import Any, Dict, List, Optional
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session

from app.models.observability_v10_models import ComplianceReport, ReportExecution, ComplianceEvidence
from app.services.observability.compliance_service import ComplianceEvidenceService
from app.services.observability.telemetry_service import TelemetryService
from app.services.observability.capacity_service import CapacityPlanningService
from app.services.observability.rpo_monitor import BackupObjectiveMonitor

logger = logging.getLogger(__name__)

SUPPORTED_REPORT_TYPES = {
    "backup_operations",
    "recovery_readiness",
    "security_controls",
    "access_control",
    "retention",
    "immutability",
    "replication",
    "audit_activity",
    "fleet_health",
    "capacity_forecast",
    "comprehensive_compliance"
}


class ReportGeneratorService:
    """Compiles and exports enterprise compliance and operational reports."""

    def __init__(self, db: Session, reports_dir: Optional[str] = None):
        self.db = db
        self.reports_dir = reports_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "reports_storage"
        )
        os.makedirs(self.reports_dir, exist_ok=True)

    def generate_report(
        self,
        report_type: str,
        title: Optional[str] = None,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
        scope: str = "GLOBAL",
        generated_by: str = "SYSTEM"
    ) -> ComplianceReport:
        """Compile factual operational data into a structured ComplianceReport entity."""
        if report_type not in SUPPORTED_REPORT_TYPES:
            raise ValueError(f"Unsupported report type: {report_type}")

        end = period_end or datetime.now(timezone.utc)
        start = period_start or (end - timedelta(days=30))
        report_id = f"RPT-{report_type.upper()}-{uuid.uuid4().hex[:8].upper()}"
        report_title = title or f"Enterprise {report_type.replace('_', ' ').title()} Report"

        # Evidence gathering based on report type
        ev_service = ComplianceEvidenceService(self.db)
        data_sources = ["RetroVault DB", "Telemetry Engine", "CAS Index"]
        evidence_summary: Dict[str, Any] = {}
        exceptions: List[str] = []
        unknowns: List[str] = []

        if report_type == "backup_operations":
            telemetry = TelemetryService(self.db)
            perf = telemetry.get_backup_performance_analytics("30d")
            ev_exec = ev_service.evaluate_domain("backup_execution", start, end)
            ev_succ = ev_service.evaluate_domain("backup_success", start, end)
            evidence_summary = {
                "backup_execution_status": ev_exec.status,
                "backup_success_status": ev_succ.status,
                "performance_analytics": perf
            }
        elif report_type == "recovery_readiness":
            ev_rest = ev_service.evaluate_domain("restore_tests", start, end)
            rpo_monitor = BackupObjectiveMonitor(self.db)
            fleet_rpo = rpo_monitor.evaluate_fleet_rpo(limit=50)
            evidence_summary = {
                "restore_readiness": ev_rest.status,
                "rpo_attainment_summary": fleet_rpo.get("summary", {}),
                "total_clients_evaluated": fleet_rpo.get("total_evaluated", 0)
            }
        elif report_type in ("security_controls", "access_control"):
            ev_acc = ev_service.evaluate_domain("access_control", start, end)
            ev_mfa = ev_service.evaluate_domain("mfa", start, end)
            ev_sec = ev_service.evaluate_domain("security_incidents", start, end)
            evidence_summary = {
                "access_control": ev_acc.evidence_summary,
                "mfa_status": ev_mfa.evidence_summary,
                "security_incidents": ev_sec.evidence_summary
            }
        elif report_type in ("retention", "immutability"):
            ev_ret = ev_service.evaluate_domain("retention", start, end)
            ev_imm = ev_service.evaluate_domain("immutability", start, end)
            evidence_summary = {
                "retention_status": ev_ret.evidence_summary,
                "immutability_status": ev_imm.evidence_summary
            }
        elif report_type == "replication":
            ev_rep = ev_service.evaluate_domain("replication", start, end)
            evidence_summary = {"replication_operations": ev_rep.evidence_summary}
        elif report_type == "audit_activity":
            ev_aud = ev_service.evaluate_domain("audit_events", start, end)
            evidence_summary = {"audit_trail": ev_aud.evidence_summary}
        elif report_type == "fleet_health":
            rpo_monitor = BackupObjectiveMonitor(self.db)
            fleet = rpo_monitor.evaluate_fleet_rpo()
            evidence_summary = {"fleet_rpo_summary": fleet}
        elif report_type == "capacity_forecast":
            from app.models.storage_repository import StorageRepository
            cap_service = CapacityPlanningService(self.db)
            repos = list(self.db.scalars(select(StorageRepository)).all())
            forecasts = []
            for r in repos:
                fc = cap_service.calculate_forecast(r.id)
                forecasts.append(fc)
            evidence_summary = {"repository_forecasts": forecasts}
        elif report_type == "comprehensive_compliance":
            all_ev = ev_service.evaluate_all_domains(start, end)
            evidence_summary = {e.domain: {"status": e.status, "summary": e.evidence_summary} for e in all_ev}

        report = ComplianceReport(
            report_id=report_id,
            report_type=report_type,
            title=report_title,
            period_start=start,
            period_end=end,
            scope=scope,
            data_sources_json=json.dumps(data_sources),
            system_version="10.0.0",
            evidence_summary_json=json.dumps(evidence_summary, indent=2),
            exceptions_json=json.dumps(exceptions) if exceptions else None,
            unknowns_json=json.dumps(unknowns) if unknowns else None,
            generated_by=generated_by,
            generated_at=datetime.now(timezone.utc)
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def export_report(self, report_id: str, export_format: str) -> ReportExecution:
        """Export report to JSON, CSV, or PDF artifact and log ReportExecution."""
        fmt = export_format.upper()
        if fmt not in ("JSON", "CSV", "PDF"):
            raise ValueError(f"Unsupported format: {export_format}")

        report = self.db.scalar(select(ComplianceReport).where(ComplianceReport.report_id == report_id))
        if not report:
            raise ValueError(f"Report {report_id} not found")

        execution_id = f"EXEC-{fmt}-{uuid.uuid4().hex[:8].upper()}"
        file_name = f"{report.report_id}.{fmt.lower()}"
        file_path = os.path.join(self.reports_dir, file_name)

        evidence_data = json.loads(report.evidence_summary_json)

        if fmt == "JSON":
            payload = {
                "report_id": report.report_id,
                "title": report.title,
                "report_type": report.report_type,
                "period_start": report.period_start.isoformat(),
                "period_end": report.period_end.isoformat(),
                "system_version": report.system_version,
                "scope": report.scope,
                "generated_at": report.generated_at.isoformat(),
                "evidence": evidence_data
            }
            content_bytes = json.dumps(payload, indent=2).encode("utf-8")
            with open(file_path, "wb") as f:
                f.write(content_bytes)

        elif fmt == "CSV":
            output = StringIO()
            writer = csv.writer(output)
            writer.writerow(["REPORT_ID", report.report_id])
            writer.writerow(["TITLE", report.title])
            writer.writerow(["TYPE", report.report_type])
            writer.writerow(["PERIOD_START", report.period_start.isoformat()])
            writer.writerow(["PERIOD_END", report.period_end.isoformat()])
            writer.writerow(["GENERATED_AT", report.generated_at.isoformat()])
            writer.writerow([])
            writer.writerow(["SECTION", "VALUE"])
            for k, v in evidence_data.items():
                writer.writerow([k, json.dumps(v) if isinstance(v, (dict, list)) else str(v)])
            content_bytes = output.getvalue().encode("utf-8")
            with open(file_path, "wb") as f:
                f.write(content_bytes)

        elif fmt == "PDF":
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas

            c = canvas.Canvas(file_path, pagesize=letter)
            c.setFont("Helvetica-Bold", 16)
            c.drawString(50, 750, f"RetroVault Enterprise Report: {report.title}")
            c.setFont("Helvetica", 10)
            c.drawString(50, 730, f"Report ID: {report.report_id} | Type: {report.report_type} | Version: {report.system_version}")
            c.drawString(50, 715, f"Period: {report.period_start.isoformat()} to {report.period_end.isoformat()}")
            c.drawString(50, 700, f"Scope: {report.scope} | Generated By: {report.generated_by}")
            c.line(50, 690, 550, 690)

            c.setFont("Helvetica-Bold", 12)
            c.drawString(50, 670, "Factual Evidence Summary:")

            y = 650
            c.setFont("Helvetica", 9)
            for k, v in list(evidence_data.items())[:25]:
                val_str = str(v) if not isinstance(v, (dict, list)) else json.dumps(v)[:90]
                c.drawString(55, y, f"- {k}: {val_str}")
                y -= 18
                if y < 80:
                    c.showPage()
                    y = 750

            c.save()
            with open(file_path, "rb") as f:
                content_bytes = f.read()

        file_size = len(content_bytes)
        checksum = hashlib.sha256(content_bytes).hexdigest()

        execution = ReportExecution(
            execution_id=execution_id,
            report_id=report.report_id,
            format=fmt,
            status="COMPLETED",
            file_path=file_path,
            file_size_bytes=file_size,
            checksum_sha256=checksum,
            created_at=datetime.now(timezone.utc)
        )
        self.db.add(execution)
        self.db.commit()
        self.db.refresh(execution)
        return execution
