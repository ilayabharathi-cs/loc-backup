"""Compliance Evidence & Governance REST API router for RetroVault V10."""

import json
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from app.database.session import get_db
from app.models.user import User
from app.models.observability_v10_models import ComplianceEvidence, ComplianceReport
from app.security.dependencies import get_current_user
from app.schemas.v10_schemas import (
    ComplianceEvidenceResponse,
    ReportGenerateRequest,
    ComplianceReportResponse
)
from app.services.observability.compliance_service import ComplianceEvidenceService, COMPLIANCE_DOMAINS
from app.services.observability.report_generator import ReportGeneratorService

router = APIRouter(prefix="/compliance", tags=["Compliance & Governance"])


@router.get("/")
def get_compliance_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve compliance summary across all 13 factual domains."""
    ev_service = ComplianceEvidenceService(db)
    records = ev_service.evaluate_all_domains()

    status_counts = {"EVIDENCE_AVAILABLE": 0, "EVIDENCE_MISSING": 0, "NOT_APPLICABLE": 0, "UNKNOWN": 0}
    domain_map = {}
    for r in records:
        status_counts[r.status] = status_counts.get(r.status, 0) + 1
        domain_map[r.domain] = {
            "evidence_id": r.evidence_id,
            "status": r.status,
            "summary": r.evidence_summary,
            "verification_hash": r.verification_hash,
            "evaluated_at": r.evaluated_at.isoformat()
        }

    return {
        "framework": "RetroVault Enterprise Factual Compliance Model",
        "legal_claim_disclaimer": "Factual system evidence only. Not autonomous legal certification.",
        "domains_total": len(COMPLIANCE_DOMAINS),
        "status_distribution": status_counts,
        "domains": domain_map
    }


@router.get("/evidence", response_model=List[ComplianceEvidenceResponse])
def list_compliance_evidence(
    domain: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List tamper-evident compliance evidence records."""
    stmt = select(ComplianceEvidence)
    if domain:
        stmt = stmt.where(ComplianceEvidence.domain == domain)
    if status_filter:
        stmt = stmt.where(ComplianceEvidence.status == status_filter)

    stmt = stmt.order_by(desc(ComplianceEvidence.evaluated_at)).offset(offset).limit(limit)
    rows = list(db.scalars(stmt).all())

    return [
        ComplianceEvidenceResponse(
            evidence_id=r.evidence_id,
            domain=r.domain,
            status=r.status,
            resource_type=r.resource_type,
            resource_id=r.resource_id,
            period_start=r.period_start.isoformat(),
            period_end=r.period_end.isoformat(),
            evidence_summary=r.evidence_summary,
            verification_hash=r.verification_hash,
            evaluated_at=r.evaluated_at.isoformat()
        )
        for r in rows
    ]


@router.post("/evaluate")
def evaluate_compliance_evidence(
    domain: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Trigger factual evidence evaluation across compliance domains."""
    ev_service = ComplianceEvidenceService(db)
    if domain:
        rec = ev_service.evaluate_domain(domain, datetime.now(timezone.utc), datetime.now(timezone.utc))
        return {"status": "SUCCESS", "evidence_id": rec.evidence_id, "evidence_status": rec.status}
    records = ev_service.evaluate_all_domains()
    return {"status": "SUCCESS", "evaluated_count": len(records)}


@router.get("/reports", response_model=List[ComplianceReportResponse])
def list_compliance_reports(
    report_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List compliance reports."""
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


@router.post("/reports", response_model=ComplianceReportResponse)
def generate_compliance_report(
    payload: ReportGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate a new auditable compliance report."""
    rep_service = ReportGeneratorService(db)
    r = rep_service.generate_report(
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
