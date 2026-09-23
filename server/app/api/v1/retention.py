from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database.session import get_db
from app.models.retention_policy import RetentionPolicy, RetentionEvaluation
from app.models.recovery_point import RecoveryPoint
from app.schemas.retention import (
    RetentionPolicyCreate,
    RetentionPolicyUpdate,
    RetentionPolicyResponse,
    RetentionEvaluationTrigger,
    RetentionEvaluationResponse,
    ManualProtectionRequest,
)
from app.schemas.backup import RecoveryPointResponse
from app.schemas.common import ApiResponse
from app.security.dependencies import get_optional_current_user
from app.services.retention.retention_engine import RetentionEngine

router = APIRouter(tags=["Retention & GFS"])


@router.post("/retention/policies", response_model=ApiResponse[RetentionPolicyResponse], status_code=status.HTTP_201_CREATED)
def create_retention_policy(
    payload: RetentionPolicyCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_optional_current_user),
):
    """Create a new GFS retention policy."""
    policy = RetentionPolicy(**payload.model_dump())
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return ApiResponse(success=True, data=RetentionPolicyResponse.model_validate(policy), message="Retention policy created")


@router.get("/retention/policies", response_model=ApiResponse[List[RetentionPolicyResponse]])
def list_retention_policies(
    db: Session = Depends(get_db),
    current_user=Depends(get_optional_current_user),
):
    """List all retention policies."""
    policies = db.execute(select(RetentionPolicy)).scalars().all()
    return ApiResponse(
        success=True,
        data=[RetentionPolicyResponse.model_validate(p) for p in policies],
        message=f"Retrieved {len(policies)} retention policies",
    )


@router.get("/retention/policies/{policy_id}", response_model=ApiResponse[RetentionPolicyResponse])
def get_retention_policy(
    policy_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_optional_current_user),
):
    """Get retention policy by ID."""
    policy = db.get(RetentionPolicy, policy_id)
    if not policy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Retention policy not found")
    return ApiResponse(success=True, data=RetentionPolicyResponse.model_validate(policy), message="Retention policy retrieved")


@router.put("/retention/policies/{policy_id}", response_model=ApiResponse[RetentionPolicyResponse])
def update_retention_policy(
    policy_id: int,
    payload: RetentionPolicyUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_optional_current_user),
):
    """Update a retention policy."""
    policy = db.get(RetentionPolicy, policy_id)
    if not policy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Retention policy not found")

    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(policy, field, val)

    db.commit()
    db.refresh(policy)
    return ApiResponse(success=True, data=RetentionPolicyResponse.model_validate(policy), message="Retention policy updated")


@router.delete("/retention/policies/{policy_id}", response_model=ApiResponse[dict])
def delete_retention_policy(
    policy_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_optional_current_user),
):
    """Delete a retention policy."""
    policy = db.get(RetentionPolicy, policy_id)
    if not policy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Retention policy not found")
    db.delete(policy)
    db.commit()
    return ApiResponse(success=True, data={"id": policy_id}, message="Retention policy deleted")


@router.post("/retention/evaluate", response_model=ApiResponse[List[RetentionEvaluationResponse]])
def evaluate_retention(
    payload: RetentionEvaluationTrigger = RetentionEvaluationTrigger(),
    db: Session = Depends(get_db),
    current_user=Depends(get_optional_current_user),
):
    """Trigger retention & GFS evaluation across recovery points."""
    evaluations = RetentionEngine.evaluate_policy(
        db,
        retention_policy_id=payload.retention_policy_id,
        client_id=payload.client_id,
    )
    return ApiResponse(
        success=True,
        data=[RetentionEvaluationResponse.model_validate(e) for e in evaluations],
        message=f"Retention evaluation completed with {len(evaluations)} policy runs",
    )


@router.get("/retention/evaluations", response_model=ApiResponse[List[RetentionEvaluationResponse]])
def list_retention_evaluations(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_optional_current_user),
):
    """List recent retention evaluation records."""
    stmt = select(RetentionEvaluation).order_by(RetentionEvaluation.evaluated_at.desc()).limit(limit)
    records = db.execute(stmt).scalars().all()
    return ApiResponse(
        success=True,
        data=[RetentionEvaluationResponse.model_validate(r) for r in records],
        message=f"Retrieved {len(records)} retention evaluations",
    )


@router.post("/recovery-points/{point_id}/protect", response_model=ApiResponse[RecoveryPointResponse])
def toggle_point_protection(
    point_id: int,
    payload: ManualProtectionRequest = ManualProtectionRequest(protect=True),
    db: Session = Depends(get_db),
    current_user=Depends(get_optional_current_user),
):
    """Protect or unprotect a specific recovery point from expiration."""
    rp = RetentionEngine.toggle_manual_protection(db, point_id, payload.protect)
    if not rp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recovery point not found")
    return ApiResponse(
        success=True,
        data=RecoveryPointResponse.model_validate(rp),
        message=f"Recovery point {'protected' if payload.protect else 'unprotected'}",
    )
