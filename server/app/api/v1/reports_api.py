"""Enterprise Reports REST API router for RetroVault V10."""

import os
import json
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from app.database.session import get_db
from app.models.user import User
from app.models.observability_v10_models import ComplianceReport, ReportExecution
from app.security.dependencies import get_current_user
from app.schemas.v10_schemas import (
    ReportGenerateRequest,
    ReportExportRequest,
    ComplianceReportResponse,
    ReportExecutionResponse
)
from app.services.observability.report_generator import ReportGeneratorService

router = APIRouter(prefix="/reports", tags=["Enterprise Reports"])


@router.get("/", response_model=List[ComplianceReportResponse])
def list_reports(
    report_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List generated enterprise reports."""
    stmt = select(ComplianceReport)
    if report_type:
        stmt = stmt.where(ComplianceReport.report_type == report_type)
    stmt = stmt.order_by(desc(ComplianceReport.generated_at)).offset(offset).limit(limit)
    reports = list(db.scalars(stmt).all())

    return [
        ComplianceReportResponse(
            report_id=r.report_id,
            report_type=r.report_type,
            title=r.title,
            period_start=r.period_start.isoformat(),
            period_end=r.period_end.isoformat(),
            scope=r.scope,
            system_version=r.system_version,
            generated_by=r.generated_by,
            generated_at=r.generated_at.isoformat(),
            evidence_summary=json.loads(r.evidence_summary_json)
        )
        for r in reports
    ]


@router.post("/", response_model=ComplianceReportResponse)
def create_report(
    payload: ReportGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate a new enterprise report."""
    generator = ReportGeneratorService(db)
    r = generator.generate_report(
        report_type=payload.report_type,
        title=payload.title,
        scope=payload.scope,
        generated_by=current_user.username
    )
    return ComplianceReportResponse(
        report_id=r.report_id,
        report_type=r.report_type,
        title=r.title,
        period_start=r.period_start.isoformat(),
        period_end=r.period_end.isoformat(),
        scope=r.scope,
        system_version=r.system_version,
        generated_by=r.generated_by,
        generated_at=r.generated_at.isoformat(),
        evidence_summary=json.loads(r.evidence_summary_json)
    )


@router.get("/{report_id}", response_model=ComplianceReportResponse)
def get_report(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get details for an individual report."""
    r = db.scalar(select(ComplianceReport).where(ComplianceReport.report_id == report_id))
    if not r:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
    return ComplianceReportResponse(
        report_id=r.report_id,
        report_type=r.report_type,
        title=r.title,
        period_start=r.period_start.isoformat(),
        period_end=r.period_end.isoformat(),
        scope=r.scope,
        system_version=r.system_version,
        generated_by=r.generated_by,
        generated_at=r.generated_at.isoformat(),
        evidence_summary=json.loads(r.evidence_summary_json)
    )


@router.post("/{report_id}/export", response_model=ReportExecutionResponse)
def export_report(
    report_id: str,
    payload: ReportExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Export report as JSON, CSV, or PDF artifact."""
    generator = ReportGeneratorService(db)
    try:
        exec_record = generator.export_report(report_id, payload.format)
        return ReportExecutionResponse(
            execution_id=exec_record.execution_id,
            report_id=exec_record.report_id,
            format=exec_record.format,
            status=exec_record.status,
            file_path=exec_record.file_path,
            file_size_bytes=exec_record.file_size_bytes,
            checksum_sha256=exec_record.checksum_sha256,
            created_at=exec_record.created_at.isoformat()
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{report_id}/download")
def download_report_file(
    report_id: str,
    format: str = Query("JSON"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Download exported artifact file."""
    exec_record = db.scalar(
        select(ReportExecution)
        .where(
            ReportExecution.report_id == report_id,
            ReportExecution.format == format.upper()
        )
        .order_by(desc(ReportExecution.created_at))
        .limit(1)
    )
    if not exec_record or not exec_record.file_path or not os.path.exists(exec_record.file_path):
        # Auto-export if not yet rendered
        generator = ReportGeneratorService(db)
        exec_record = generator.export_report(report_id, format)

    media_type = "application/json"
    if format.upper() == "CSV":
        media_type = "text/csv"
    elif format.upper() == "PDF":
        media_type = "application/pdf"

    return FileResponse(
        path=exec_record.file_path,
        filename=os.path.basename(exec_record.file_path),
        media_type=media_type
    )
