"""Replication API router for RetroVault V7."""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.storage_repository import StorageRepository
from app.models.replication import ReplicationJob, ReplicationItem
from app.schemas.common import ApiResponse
from app.schemas.v7_schemas import (
    ReplicationJobCreate, ReplicationJobResponse, ReplicationItemResponse, TopologyResponse
)
from app.security.dependencies import require_role, get_optional_current_user
from app.services.replication.engine import ReplicationEngine
from app.services.replication.topology import BackupTopologyEvaluator
from app.services.audit_service import log_audit_event

router = APIRouter(prefix="/replication", tags=["Replication Engine"])


@router.get("/jobs", response_model=ApiResponse[List[ReplicationJobResponse]])
def list_replication_jobs(
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db)
):
    """List all replication jobs."""
    query = db.query(ReplicationJob)
    if status:
        query = query.filter(ReplicationJob.status == status)
    jobs = query.order_by(ReplicationJob.created_at.desc()).all()
    return ApiResponse(
        success=True,
        data=[ReplicationJobResponse.model_validate(j) for j in jobs],
        message=f"Retrieved {len(jobs)} replication jobs"
    )


@router.post("/jobs", response_model=ApiResponse[ReplicationJobResponse], status_code=status.HTTP_201_CREATED)
def create_replication_job(
    request: ReplicationJobCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["admin", "operator"]))
):
    """Create and optionally start a new replication job."""
    source_repo = db.query(StorageRepository).filter(StorageRepository.id == request.source_repository_id).first()
    dest_repo = db.query(StorageRepository).filter(StorageRepository.id == request.destination_repository_id).first()

    if not source_repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Source repository #{request.source_repository_id} not found")
    if not dest_repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Destination repository #{request.destination_repository_id} not found")

    job_id_str = f"REPL-{uuid.uuid4().hex[:8].upper()}"

    job = ReplicationJob(
        job_id=job_id_str,
        source_repository_id=source_repo.id,
        destination_repository_id=dest_repo.id,
        recovery_point_id=request.recovery_point_id,
        bandwidth_limit_mbps=request.bandwidth_limit_mbps,
        status="CREATED"
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    engine = ReplicationEngine(db, job)
    engine.plan_replication()

    if request.execute_now:
        engine.execute_replication()

    log_audit_event(
        db=db,
        action="REPLICATION_JOB_CREATED",
        resource_type="replication",
        resource_id=job.job_id,
        user_id=current_user.id if current_user else None,
        details=f"Created replication job {job.job_id} from {source_repo.name} to {dest_repo.name}"
    )

    return ApiResponse(
        success=True,
        data=ReplicationJobResponse.model_validate(job),
        message="Replication job created successfully"
    )


@router.get("/jobs/{job_id}", response_model=ApiResponse[ReplicationJobResponse])
def get_replication_job(job_id: str, db: Session = Depends(get_db)):
    """Retrieve details for a replication job."""
    job = None
    if job_id.isdigit():
        job = db.query(ReplicationJob).filter(ReplicationJob.id == int(job_id)).first()
    if not job:
        job = db.query(ReplicationJob).filter(ReplicationJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Replication job '{job_id}' not found")

    return ApiResponse(success=True, data=ReplicationJobResponse.model_validate(job), message="Replication job retrieved")


@router.get("/jobs/{job_id}/items", response_model=ApiResponse[List[ReplicationItemResponse]])
def get_replication_items(job_id: str, db: Session = Depends(get_db)):
    """Retrieve object-level items for a replication job."""
    job = None
    if job_id.isdigit():
        job = db.query(ReplicationJob).filter(ReplicationJob.id == int(job_id)).first()
    if not job:
        job = db.query(ReplicationJob).filter(ReplicationJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Replication job '{job_id}' not found")

    items = db.query(ReplicationItem).filter(ReplicationItem.job_id == job.id).order_by(ReplicationItem.id.asc()).all()
    return ApiResponse(
        success=True,
        data=[ReplicationItemResponse.model_validate(i) for i in items],
        message=f"Retrieved {len(items)} replication items"
    )


@router.post("/jobs/{job_id}/start", response_model=ApiResponse[ReplicationJobResponse])
def start_replication_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["admin", "operator"]))
):
    """Start or execute a queued replication job."""
    job = db.query(ReplicationJob).filter(
        (ReplicationJob.job_id == job_id) | (ReplicationJob.id == (int(job_id) if job_id.isdigit() else -1))
    ).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Replication job not found")

    engine = ReplicationEngine(db, job)
    engine.execute_replication()
    return ApiResponse(success=True, data=ReplicationJobResponse.model_validate(job), message="Replication job executed")


@router.post("/jobs/{job_id}/pause", response_model=ApiResponse[ReplicationJobResponse])
def pause_replication_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["admin", "operator"]))
):
    """Pause an in-flight replication job."""
    job = db.query(ReplicationJob).filter(
        (ReplicationJob.job_id == job_id) | (ReplicationJob.id == (int(job_id) if job_id.isdigit() else -1))
    ).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Replication job not found")

    engine = ReplicationEngine(db, job)
    engine.pause()
    return ApiResponse(success=True, data=ReplicationJobResponse.model_validate(job), message="Replication job paused")


@router.post("/jobs/{job_id}/resume", response_model=ApiResponse[ReplicationJobResponse])
def resume_replication_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["admin", "operator"]))
):
    """Resume a paused or interrupted replication job."""
    job = db.query(ReplicationJob).filter(
        (ReplicationJob.job_id == job_id) | (ReplicationJob.id == (int(job_id) if job_id.isdigit() else -1))
    ).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Replication job not found")

    engine = ReplicationEngine(db, job)
    engine.execute_replication()
    return ApiResponse(success=True, data=ReplicationJobResponse.model_validate(job), message="Replication job resumed")


@router.post("/jobs/{job_id}/cancel", response_model=ApiResponse[ReplicationJobResponse])
def cancel_replication_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["admin", "operator"]))
):
    """Cancel a replication job."""
    job = db.query(ReplicationJob).filter(
        (ReplicationJob.job_id == job_id) | (ReplicationJob.id == (int(job_id) if job_id.isdigit() else -1))
    ).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Replication job not found")

    engine = ReplicationEngine(db, job)
    engine.cancel()
    return ApiResponse(success=True, data=ReplicationJobResponse.model_validate(job), message="Replication job cancelled")


@router.post("/jobs/{job_id}/retry", response_model=ApiResponse[ReplicationJobResponse])
def retry_failed_replication_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["admin", "operator"]))
):
    """Retry failed items in a replication job."""
    job = db.query(ReplicationJob).filter(
        (ReplicationJob.job_id == job_id) | (ReplicationJob.id == (int(job_id) if job_id.isdigit() else -1))
    ).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Replication job not found")

    engine = ReplicationEngine(db, job)
    engine.retry_failed()
    return ApiResponse(success=True, data=ReplicationJobResponse.model_validate(job), message="Retried failed replication items")


@router.get("/topology", response_model=ApiResponse[TopologyResponse])
def get_backup_topology(db: Session = Depends(get_db)):
    """Evaluate 3-2-1 backup protection rules based on actual configured repositories."""
    evaluator = BackupTopologyEvaluator(db)
    result = evaluator.evaluate_topology()
    return ApiResponse(
        success=True,
        data=TopologyResponse(**result),
        message="3-2-1 backup topology calculated"
    )
