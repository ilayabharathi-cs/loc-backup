"""Recovery Verification REST API router for RetroVault V11."""

import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database.session import get_db
from app.models.user import User
from app.models.workload_v11_models import RecoveryVerification, RecoveryVerificationStep
from app.security.dependencies import get_current_user
from app.schemas.v11_schemas import (
    RecoveryVerificationCreate,
    RecoveryVerificationResponse
)
from app.services.workload.recovery_verification import RecoveryVerificationEngine

router = APIRouter(prefix="/recovery-verification", tags=["Recovery Verification"])


def _serialize_verification(v: RecoveryVerification) -> dict:
    steps = [
        {
            "step_name": s.step_name,
            "step_order": s.step_order,
            "status": s.status,
            "details": json.loads(s.details_json or "{}") if s.details_json else None,
            "error_message": s.error_message
        }
        for s in (v.steps or [])
    ]
    return {
        "id": v.id,
        "verification_id": v.verification_id,
        "recovery_point_id": v.recovery_point_id,
        "workload_id": v.workload_id,
        "verification_type": v.verification_type,
        "sandbox_path": v.sandbox_path,
        "status": v.status,
        "duration_ms": v.duration_ms,
        "error_message": v.error_message,
        "evidence": json.loads(v.evidence_json or "{}") if v.evidence_json else None,
        "created_at": v.created_at.isoformat(),
        "started_at": v.started_at.isoformat() if v.started_at else None,
        "completed_at": v.completed_at.isoformat() if v.completed_at else None,
        "steps": steps
    }


@router.get("/")
def list_verifications(
    workload_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List recovery verification executions."""
    stmt = select(RecoveryVerification).order_by(RecoveryVerification.id.desc())
    if workload_id:
        stmt = stmt.where(RecoveryVerification.workload_id == workload_id)
    if status:
        stmt = stmt.where(RecoveryVerification.status == status)
    records = db.execute(stmt).scalars().all()
    return [_serialize_verification(r) for r in records]


@router.post("/", status_code=status.HTTP_201_CREATED)
def trigger_verification(
    req: RecoveryVerificationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Queue and execute a synthetic restore verification job."""
    engine = RecoveryVerificationEngine(db)
    rec = engine.trigger_verification(
        recovery_point_id=req.recovery_point_id,
        workload_id=req.workload_id,
        verification_type=req.verification_type,
        initiated_by=current_user.username if current_user else "USER"
    )
    # Execute verification synchronously
    exec_res = engine.execute_verification(rec.verification_id)
    db.refresh(rec)
    return _serialize_verification(rec)


@router.get("/{verification_id}")
def get_verification(
    verification_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get single recovery verification status and step results."""
    stmt = select(RecoveryVerification).where(RecoveryVerification.verification_id == verification_id)
    rec = db.execute(stmt).scalars().first()
    if not rec:
        raise HTTPException(status_code=404, detail=f"Verification '{verification_id}' not found")
    return _serialize_verification(rec)


@router.post("/{verification_id}/retry")
def retry_verification(
    verification_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retry a failed recovery verification execution."""
    stmt = select(RecoveryVerification).where(RecoveryVerification.verification_id == verification_id)
    rec = db.execute(stmt).scalars().first()
    if not rec:
        raise HTTPException(status_code=404, detail=f"Verification '{verification_id}' not found")

    engine = RecoveryVerificationEngine(db)
    new_verif = engine.trigger_verification(
        recovery_point_id=rec.recovery_point_id,
        workload_id=rec.workload_id,
        verification_type=rec.verification_type,
        initiated_by=current_user.username if current_user else "USER"
    )
    engine.execute_verification(new_verif.verification_id)
    db.refresh(new_verif)
    return _serialize_verification(new_verif)
