"""API Router for V8 Integrity Scans, Mass-Deletion Guard & Immutability."""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.models.storage_repository import StorageRepository
from app.models.security_v8_models import IntegrityScan, DeletionGuard
from app.schemas.v8_schemas import (
    IntegrityScanTrigger,
    IntegrityScanResponse,
    DeletionGuardRequest,
    DeletionGuardApproval,
    DeletionGuardResponse,
)
from app.services.security.integrity_monitor import IntegrityMonitor
from app.services.security.deletion_guard import DeletionGuardService
from app.services.repository.immutable_provider import ImmutabilityProvider

router = APIRouter(prefix="/security-ops", tags=["v8_security_ops"])


# Integrity Scans
@router.get("/integrity/scans", response_model=List[IntegrityScanResponse])
def list_integrity_scans(
    repository_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(IntegrityScan)
    if repository_id:
        query = query.filter(IntegrityScan.repository_id == repository_id)
    return query.order_by(IntegrityScan.created_at.desc()).limit(limit).all()


@router.post("/integrity/scan")
def trigger_integrity_scan(
    trigger_in: IntegrityScanTrigger,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    monitor = IntegrityMonitor(db, repository_id=trigger_in.repository_id)
    result = monitor.run_integrity_scan(
        repository_id=trigger_in.repository_id,
        scan_type=trigger_in.scan_type,
        sample_limit=trigger_in.sample_limit
    )
    return result


# Deletion Guard
@router.get("/deletion-guard/requests", response_model=List[DeletionGuardResponse])
def list_deletion_guard_requests(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(DeletionGuard)
    if status:
        query = query.filter(DeletionGuard.status == status.upper())
    return query.order_by(DeletionGuard.created_at.desc()).all()


@router.post("/deletion-guard/request")
def submit_deletion_request(
    guard_in: DeletionGuardRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    guard_svc = DeletionGuardService(db)
    result = guard_svc.evaluate_request(
        request_type=guard_in.request_type,
        target_resource_type=guard_in.target_resource_type,
        target_resource_id=guard_in.target_resource_id,
        payload=guard_in.payload,
        requester_username=current_user.username,
        requester_id=current_user.id
    )
    return result


@router.post("/deletion-guard/requests/{guard_id}/approve")
def approve_deletion_request(
    guard_id: int,
    approval_in: DeletionGuardApproval,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    guard_svc = DeletionGuardService(db)
    # Check if MFA token is supplied
    mfa_valid = bool(approval_in.mfa_code and len(approval_in.mfa_code) == 6)
    result = guard_svc.approve_request(
        guard_id=guard_id,
        approver_username=current_user.username,
        mfa_verified=mfa_valid
    )
    if not result.get("success", True):
        raise HTTPException(status_code=400, detail=result.get("error", "Approval failed"))
    return result


@router.post("/deletion-guard/requests/{guard_id}/reject")
def reject_deletion_request(
    guard_id: int,
    reason: str = "Rejected by administrator",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    guard_svc = DeletionGuardService(db)
    result = guard_svc.reject_request(guard_id=guard_id, rejector_username=current_user.username, reason=reason)
    return result


# Repository Immutability Capabilities
@router.get("/repositories/{repo_id}/capabilities")
def get_repository_immutability_capabilities(
    repo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = db.query(StorageRepository).filter(StorageRepository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    provider = ImmutabilityProvider(db)
    caps = provider.get_repository_capabilities(repo)
    return caps


@router.post("/repositories/{repo_id}/set-immutability")
def set_repository_immutability(
    repo_id: int,
    immutability_state: str,
    retention_days: int = 30,
    provider_mode: str = "COMPLIANCE",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    provider = ImmutabilityProvider(db)
    result = provider.set_repository_immutability(
        repository_id=repo_id,
        immutability_state=immutability_state,
        retention_days=retention_days,
        provider_mode=provider_mode
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to set immutability"))
    return result
