"""Safe Remediation REST API router for RetroVault V11."""

import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database.session import get_db
from app.models.user import User
from app.models.workload_v11_models import RemediationAction
from app.security.dependencies import get_current_user
from app.schemas.v11_schemas import (
    RemediationProposeRequest,
    RemediationActionResponse
)
from app.services.workload.remediation_service import RemediationService

router = APIRouter(prefix="/remediations", tags=["Remediations"])


def _serialize_remediation(r: RemediationAction) -> dict:
    return {
        "id": r.id,
        "remediation_id": r.remediation_id,
        "action_type": r.action_type,
        "target_resource_type": r.target_resource_type,
        "target_resource_id": r.target_resource_id,
        "requires_dual_approval": r.requires_dual_approval,
        "first_approver": r.first_approver,
        "second_approver": r.second_approver,
        "status": r.status,
        "execution_result": json.loads(r.execution_result_json or "{}") if r.execution_result_json else None,
        "created_at": r.created_at.isoformat(),
        "executed_at": r.executed_at.isoformat() if r.executed_at else None
    }


@router.get("/")
def list_remediations(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List remediation actions."""
    stmt = select(RemediationAction).order_by(RemediationAction.id.desc())
    if status:
        stmt = stmt.where(RemediationAction.status == status)
    rems = db.execute(stmt).scalars().all()
    return [_serialize_remediation(r) for r in rems]


@router.post("/", status_code=status.HTTP_201_CREATED)
def propose_remediation(
    req: RemediationProposeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Propose a safe remediation workflow. Autonomous destructive actions are rejected."""
    svc = RemediationService(db)
    try:
        rem = svc.propose_remediation(
            action_type=req.action_type,
            target_resource_type=req.target_resource_type,
            target_resource_id=req.target_resource_id,
            proposed_by=current_user.username if current_user else "USER",
            requires_dual_approval=req.requires_dual_approval
        )
        return _serialize_remediation(rem)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{remediation_id}/approve")
def approve_remediation(
    remediation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Approve a proposed remediation."""
    svc = RemediationService(db)
    try:
        rem = svc.approve_remediation(
            remediation_id=remediation_id,
            approver=current_user.username if current_user else "APPROVER"
        )
        return _serialize_remediation(rem)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{remediation_id}/execute")
def execute_remediation(
    remediation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Execute an approved remediation."""
    svc = RemediationService(db)
    res = svc.execute_remediation(
        remediation_id=remediation_id,
        executor=current_user.username if current_user else "EXECUTOR"
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "Execution failed"))
    return res
