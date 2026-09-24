"""Repositories API router for RetroVault V7."""

import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.storage_repository import StorageRepository
from app.schemas.common import ApiResponse
from app.schemas.v7_schemas import StorageRepositoryCreate, StorageRepositoryResponse, RepositoryHealthResponse
from app.security.dependencies import require_role, get_optional_current_user
from app.services.repository.health_monitor import RepositoryHealthMonitor
from app.services.audit_service import log_audit_event

router = APIRouter(prefix="/repositories", tags=["Repository Management"])


@router.get("", response_model=ApiResponse[List[StorageRepositoryResponse]])
def list_repositories(db: Session = Depends(get_db)):
    """List all configured storage repositories."""
    repos = db.query(StorageRepository).order_by(StorageRepository.id.asc()).all()
    return ApiResponse(
        success=True,
        data=[StorageRepositoryResponse.model_validate(r) for r in repos],
        message=f"Retrieved {len(repos)} repositories"
    )


@router.post("", response_model=ApiResponse[StorageRepositoryResponse], status_code=status.HTTP_201_CREATED)
def create_repository(
    request: StorageRepositoryCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["admin", "operator"]))
):
    """Register a new storage repository (LOCAL_FILESYSTEM, REMOTE_FILESYSTEM, S3_COMPATIBLE)."""
    existing = db.query(StorageRepository).filter(StorageRepository.name == request.name).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Repository '{request.name}' already exists")

    cfg_str = json.dumps(request.configuration) if request.configuration else None

    repo = StorageRepository(
        name=request.name,
        repository_type=request.repository_type,
        path=request.path,
        endpoint=request.endpoint,
        root_path=request.root_path or request.path,
        total_bytes=request.total_bytes,
        used_bytes=0,
        available_bytes=request.total_bytes,
        status=request.status,
        protection_mode=request.protection_mode,
        encryption_enabled=request.encryption_enabled,
        configuration=cfg_str
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)

    log_audit_event(
        db=db,
        action="REPOSITORY_CREATED",
        resource_type="repository",
        resource_id=str(repo.id),
        user_id=current_user.id if current_user else None,
        details=f"Created repository {repo.name} ({repo.repository_type})"
    )

    return ApiResponse(
        success=True,
        data=StorageRepositoryResponse.model_validate(repo),
        message="Repository created successfully"
    )


@router.get("/{repo_id}", response_model=ApiResponse[StorageRepositoryResponse])
def get_repository(repo_id: int, db: Session = Depends(get_db)):
    """Get repository by ID."""
    repo = db.query(StorageRepository).filter(StorageRepository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Repository #{repo_id} not found")
    return ApiResponse(success=True, data=StorageRepositoryResponse.model_validate(repo), message="Repository retrieved")


@router.get("/{repo_id}/health", response_model=ApiResponse[RepositoryHealthResponse])
def get_repository_health(repo_id: int, db: Session = Depends(get_db)):
    """Run comprehensive repository health check probe."""
    try:
        monitor = RepositoryHealthMonitor(db)
        health = monitor.check_repository_health(repo_id)
        return ApiResponse(
            success=True,
            data=RepositoryHealthResponse(**health),
            message="Repository health check completed"
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Health check failed: {e}")


@router.post("/{repo_id}/maintenance", response_model=ApiResponse[StorageRepositoryResponse])
def set_maintenance_mode(
    repo_id: int,
    enabled: bool = Query(True, description="Enable or disable maintenance mode"),
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["admin", "operator"]))
):
    """Toggle maintenance mode on a repository."""
    repo = db.query(StorageRepository).filter(StorageRepository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Repository #{repo_id} not found")

    repo.status = "MAINTENANCE" if enabled else "ONLINE"
    db.commit()
    db.refresh(repo)

    log_audit_event(
        db=db,
        action="REPOSITORY_MAINTENANCE_TOGGLED",
        resource_type="repository",
        resource_id=str(repo.id),
        user_id=current_user.id if current_user else None,
        details=f"Maintenance mode set to {enabled} for repository {repo.name}"
    )

    return ApiResponse(
        success=True,
        data=StorageRepositoryResponse.model_validate(repo),
        message=f"Repository maintenance mode set to {enabled}"
    )


@router.delete("/{repo_id}", response_model=ApiResponse[dict])
def delete_repository(
    repo_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["admin"]))
):
    """Delete a storage repository. Protected/Immutable repositories cannot be deleted."""
    repo = db.query(StorageRepository).filter(StorageRepository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Repository #{repo_id} not found")

    if repo.protection_mode in ("PROTECTED", "IMMUTABLE"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cannot delete repository '{repo.name}' while in {repo.protection_mode} mode."
        )

    db.delete(repo)
    db.commit()

    log_audit_event(
        db=db,
        action="REPOSITORY_DELETED",
        resource_type="repository",
        resource_id=str(repo_id),
        user_id=current_user.id if current_user else None,
        details=f"Deleted repository {repo.name}"
    )

    return ApiResponse(success=True, data={"repository_id": repo_id}, message="Repository deleted")
