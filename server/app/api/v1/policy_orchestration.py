"""Policy Orchestration REST API router for RetroVault V11."""

import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database.session import get_db
from app.models.user import User
from app.models.workload_v11_models import PolicyLifecycle
from app.security.dependencies import get_current_user
from app.schemas.v11_schemas import (
    PolicyVersionCreate,
    PolicyApprovalRequest,
    PolicyRollbackRequest,
    PolicyLifecycleResponse
)
from app.services.workload.policy_orchestrator import PolicyOrchestrationService

router = APIRouter(prefix="/policy-orchestration", tags=["Policy Orchestration"])


def _serialize_lifecycle(pl: PolicyLifecycle) -> dict:
    return {
        "id": pl.id,
        "policy_id": pl.policy_id,
        "version": pl.version,
        "lifecycle_state": pl.lifecycle_state,
        "definition": json.loads(pl.definition_json or "{}"),
        "effective_at": pl.effective_at.isoformat() if pl.effective_at else None,
        "created_by": pl.created_by,
        "created_at": pl.created_at.isoformat(),
        "updated_at": pl.updated_at.isoformat()
    }


@router.get("/")
def list_policy_lifecycles(
    policy_id: Optional[str] = Query(None),
    lifecycle_state: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List policy versions and lifecycle records."""
    stmt = select(PolicyLifecycle).order_by(PolicyLifecycle.id.desc())
    if policy_id:
        stmt = stmt.where(PolicyLifecycle.policy_id == policy_id)
    if lifecycle_state:
        stmt = stmt.where(PolicyLifecycle.lifecycle_state == lifecycle_state)
    records = db.execute(stmt).scalars().all()
    return [_serialize_lifecycle(r) for r in records]


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_policy_version(
    req: PolicyVersionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new policy version in DRAFT state."""
    svc = PolicyOrchestrationService(db)
    lc = svc.create_policy_version(
        policy_id=req.policy_id,
        definition=req.definition,
        created_by=current_user.username if current_user else "USER"
    )
    return _serialize_lifecycle(lc)


@router.post("/{id}/approve")
def approve_policy_version(
    id: int,
    req: PolicyApprovalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Approve a DRAFT policy version."""
    svc = PolicyOrchestrationService(db)
    try:
        lc = svc.approve_policy_version(
            policy_lifecycle_id=id,
            approver=current_user.username if current_user else "ADMIN",
            notes=req.notes
        )
        return _serialize_lifecycle(lc)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{id}/activate")
def activate_policy_version(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Activate an APPROVED policy version."""
    svc = PolicyOrchestrationService(db)
    try:
        lc = svc.activate_policy_version(
            policy_lifecycle_id=id,
            activated_by=current_user.username if current_user else "ADMIN"
        )
        return _serialize_lifecycle(lc)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{policy_id}/rollback")
def rollback_policy(
    policy_id: str,
    req: PolicyRollbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Roll back policy to a previous version."""
    svc = PolicyOrchestrationService(db)
    try:
        lc = svc.rollback_policy(
            policy_id=policy_id,
            target_version=req.target_version,
            rolled_back_by=current_user.username if current_user else "ADMIN"
        )
        return _serialize_lifecycle(lc)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{policy_id}/affected")
def get_affected_resources(
    policy_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Compute deterministically affected workloads and clients for this policy."""
    svc = PolicyOrchestrationService(db)
    return svc.calculate_affected_resources(policy_id)
