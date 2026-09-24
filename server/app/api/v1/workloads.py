"""Workload Management REST API router for RetroVault V11."""

import json
import uuid
import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database.session import get_db
from app.models.user import User
from app.models.workload_v11_models import Workload, WorkloadProtection, WorkloadArtifact
from app.security.dependencies import get_current_user
from app.schemas.v11_schemas import (
    WorkloadCreate,
    WorkloadResponse,
    WorkloadDiscoverRequest,
    WorkloadProtectRequest,
    WorkloadRestorePreviewRequest,
    WorkloadRestoreRequest
)
from app.services.workload.discovery_service import WorkloadDiscoveryService
from app.services.workload.protection_service import WorkloadProtectionService
from app.services.workload.recovery_service import WorkloadRecoveryService
from app.services.workload.provider import (
    RestorePreviewResult,
    RestoreExecutionResult
)

router = APIRouter(prefix="/workloads", tags=["Workloads"])


def _serialize_workload(w: Workload) -> Dict[str, Any]:
    return {
        "id": w.id,
        "workload_id": w.workload_id,
        "client_id": str(w.client_id),
        "type": w.type,
        "name": w.name,
        "version": w.version,
        "status": w.status,
        "health": w.health,
        "protection_state": w.protection_state,
        "consistency_capability": w.consistency_capability,
        "last_protected_at": w.last_protected_at.isoformat() if w.last_protected_at else None,
        "last_verified_at": w.last_verified_at.isoformat() if w.last_verified_at else None,
        "config": json.loads(w.config_json or "{}"),
        "metadata": json.loads(w.metadata_json or "{}"),
        "created_at": w.created_at.isoformat(),
        "updated_at": w.updated_at.isoformat()
    }


@router.get("/")
def list_workloads(
    client_id: Optional[str] = Query(None),
    workload_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all registered application workloads with optional filtering."""
    stmt = select(Workload)
    if client_id:
        stmt = stmt.where(Workload.client_id == client_id)
    if workload_type:
        stmt = stmt.where(Workload.type == workload_type)
    workloads = db.execute(stmt).scalars().all()
    return [_serialize_workload(w) for w in workloads]


@router.get("/providers")
def list_providers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List registered workload providers and their capabilities."""
    svc = WorkloadDiscoveryService(db)
    return svc.list_providers()


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_workload(
    req: WorkloadCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Manually register an application workload."""
    workload_id = req.workload_id or f"wl-{uuid.uuid4().hex[:12]}"
    now = datetime.datetime.now(datetime.timezone.utc)
    w = Workload(
        workload_id=workload_id,
        client_id=req.client_id,
        type=req.type,
        name=req.name,
        version=req.version,
        status="DISCOVERED",
        health="HEALTHY",
        protection_state="UNPROTECTED",
        consistency_capability="UNKNOWN",
        config_json=json.dumps(req.config or {}),
        metadata_json=json.dumps({}),
        created_at=now,
        updated_at=now
    )
    db.add(w)
    db.commit()
    db.refresh(w)
    return _serialize_workload(w)


@router.get("/{workload_id}")
def get_workload(
    workload_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get workload details by workload_id."""
    stmt = select(Workload).where(Workload.workload_id == workload_id)
    w = db.execute(stmt).scalars().first()
    if not w:
        raise HTTPException(status_code=404, detail=f"Workload '{workload_id}' not found")
    return _serialize_workload(w)


@router.post("/{client_id}/discover")
def discover_workloads(
    client_id: str,
    req: WorkloadDiscoverRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Trigger capability-based workload discovery on client."""
    svc = WorkloadDiscoveryService(db)
    items = svc.discover_client_workloads(client_id, req.provider_type, req.config)
    return [_serialize_workload(w) for w in items]


@router.post("/{workload_id}/protect")
def protect_workload(
    workload_id: str,
    req: WorkloadProtectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Execute application-consistent backup for a workload."""
    svc = WorkloadProtectionService(db)
    result = svc.execute_workload_backup(
        workload_id=workload_id,
        backup_type=req.backup_type,
        initiated_by=current_user.username if current_user else "USER",
        context_override=req.context_override
    )
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Backup failed"))
    return result


@router.post("/{workload_id}/restore-preview")
def preview_restore(
    workload_id: str,
    req: WorkloadRestorePreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate restore preview, conflict analysis, and dependency report."""
    svc = WorkloadRecoveryService(db)
    preview = svc.preview_restore(
        workload_id=workload_id,
        recovery_point_id=req.recovery_point_id,
        target_destination=req.target_destination,
        recovery_mode=req.recovery_mode,
        target_client_id=req.target_client_id
    )
    return {
        "workload_id": preview.workload_id,
        "source_recovery_point_id": preview.source_recovery_point_id,
        "target_destination": preview.target_destination,
        "estimated_size_bytes": preview.estimated_size_bytes,
        "overwrite_conflicts": preview.overwrite_conflicts,
        "required_dependencies": preview.required_dependencies,
        "consistency_status": preview.consistency_status,
        "validation_plan": preview.validation_plan,
        "is_safe_to_proceed": preview.is_safe_to_proceed,
        "blockers": preview.blockers
    }


@router.post("/{workload_id}/restore")
def restore_workload(
    workload_id: str,
    req: WorkloadRestoreRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Execute verified application restore."""
    svc = WorkloadRecoveryService(db)
    res = svc.execute_application_restore(
        workload_id=workload_id,
        recovery_point_id=req.recovery_point_id,
        target_destination=req.target_destination,
        recovery_mode=req.recovery_mode,
        target_client_id=req.target_client_id
    )
    if not res.success:
        raise HTTPException(status_code=500, detail=res.error or "Restore execution failed")
    return {
        "success": res.success,
        "current_phase": res.current_phase,
        "phases_completed": res.phases_completed,
        "restored_bytes": res.restored_bytes,
        "artifacts_restored": res.artifacts_restored,
        "verification_passed": res.verification_passed,
        "validation_passed": res.validation_passed,
        "details": res.details
    }
