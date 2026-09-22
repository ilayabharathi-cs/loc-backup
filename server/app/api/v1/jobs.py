import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.backup_job import BackupJob
from app.models.backup_run import BackupRun
from app.models.client import Client
from app.models.backup_policy import BackupPolicy
from app.models.user import User
from app.schemas.job import JobCreate, JobResponse
from app.schemas.common import ApiResponse
from app.security.dependencies import require_role, get_optional_current_user
from app.services.audit_service import log_audit_event

router = APIRouter(prefix="/jobs", tags=["Backup Jobs"])

def find_job(db: Session, job_identifier: str) -> BackupJob:
    job = None
    if job_identifier.isdigit():
        job = db.query(BackupJob).filter(BackupJob.id == int(job_identifier)).first()
    if not job:
        job = db.query(BackupJob).filter(BackupJob.job_id == job_identifier).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backup job '{job_identifier}' not found"
        )
    return job

@router.get("", response_model=ApiResponse[List[JobResponse]])
def list_jobs(
    status: Optional[str] = Query(None, description="Filter by status (pending, queued, running, completed, failed, cancelled)"),
    client_id: Optional[str] = Query(None, description="Filter by client_id"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    query = db.query(BackupJob)
    if status:
        query = query.filter(BackupJob.status == status)
    if client_id:
        if client_id.isdigit():
            query = query.filter(BackupJob.client_id == int(client_id))
        else:
            client = db.query(Client).filter(Client.client_id == client_id).first()
            if client:
                query = query.filter(BackupJob.client_id == client.id)

    jobs = query.order_by(BackupJob.created_at.desc()).all()
    results = []
    for j in jobs:
        processed_mb = 0.0
        progress = 100 if j.status == "completed" else 0
        latest_run = db.query(BackupRun).filter(BackupRun.job_id == j.id).order_by(BackupRun.started_at.desc()).first()
        if latest_run:
            processed_mb = round(latest_run.bytes_processed / (1024 * 1024), 1)
            if latest_run.status == "running":
                progress = 65
            elif latest_run.status == "completed":
                progress = 100

        results.append(JobResponse(
            id=j.id,
            job_id=j.job_id,
            client_id=j.client_id,
            client_identifier=j.client.client_id if j.client else f"PC-{j.client_id:03d}",
            client_hostname=j.client.hostname if j.client else f"CLIENT-{j.client_id}",
            policy_id=j.policy_id,
            policy_name=j.policy.name if j.policy else "Default Policy",
            status=j.status,
            scheduled_at=j.scheduled_at,
            started_at=j.started_at,
            completed_at=j.completed_at,
            created_at=j.created_at,
            data_processed_mb=processed_mb,
            progress_percent=progress
        ))

    return ApiResponse(success=True, data=results, message=f"Retrieved {len(results)} jobs")

@router.get("/{job_id}", response_model=ApiResponse[JobResponse])
def get_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    j = find_job(db, job_id)
    processed_mb = 0.0
    progress = 100 if j.status == "completed" else 0
    latest_run = db.query(BackupRun).filter(BackupRun.job_id == j.id).order_by(BackupRun.started_at.desc()).first()
    if latest_run:
        processed_mb = round(latest_run.bytes_processed / (1024 * 1024), 1)
        if latest_run.status == "running":
            progress = 65
        elif latest_run.status == "completed":
            progress = 100

    res = JobResponse(
        id=j.id,
        job_id=j.job_id,
        client_id=j.client_id,
        client_identifier=j.client.client_id if j.client else f"PC-{j.client_id:03d}",
        client_hostname=j.client.hostname if j.client else f"CLIENT-{j.client_id}",
        policy_id=j.policy_id,
        policy_name=j.policy.name if j.policy else "Default Policy",
        status=j.status,
        scheduled_at=j.scheduled_at,
        started_at=j.started_at,
        completed_at=j.completed_at,
        created_at=j.created_at,
        data_processed_mb=processed_mb,
        progress_percent=progress
    )
    return ApiResponse(success=True, data=res, message="Job details retrieved")

@router.post("", response_model=ApiResponse[JobResponse], status_code=status.HTTP_201_CREATED)
def create_job(
    request: JobCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(require_role(["admin", "operator"]))
):
    client = None
    if request.client_id.isdigit():
        client = db.query(Client).filter(Client.id == int(request.client_id)).first()
    if not client:
        client = db.query(Client).filter(Client.client_id == request.client_id).first()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target client '{request.client_id}' not found"
        )

    policy_id = request.policy_id
    if not policy_id:
        policy = db.query(BackupPolicy).filter(BackupPolicy.is_active == True).first()
        policy_id = policy.id if policy else None

    # Generate unique job_id
    now = datetime.datetime.now(datetime.timezone.utc)
    job_count = db.query(BackupJob).count()
    job_id_str = f"JOB-{9400 + job_count + 1}"

    job = BackupJob(
        job_id=job_id_str,
        client_id=client.id,
        policy_id=policy_id,
        status="running",
        started_at=now
    )
    db.add(job)
    db.flush()

    # Create associated backup run
    run = BackupRun(
        job_id=job.id,
        client_id=client.id,
        backup_type="incremental",
        started_at=now,
        status="running",
        files_processed=42,
        bytes_processed=412 * 1024 * 1024,
        bytes_uploaded=412 * 1024 * 1024
    )
    db.add(run)

    # Update client status to active
    client.last_seen = now
    db.commit()
    db.refresh(job)

    log_audit_event(
        db=db,
        action="JOB_TRIGGERED",
        resource_type="job",
        resource_id=job.job_id,
        user_id=current_user.id if current_user else None,
        client_id=client.id,
        details=f"Backup job {job.job_id} initiated for client {client.hostname}"
    )

    res = JobResponse(
        id=job.id,
        job_id=job.job_id,
        client_id=job.client_id,
        client_identifier=client.client_id,
        client_hostname=client.hostname,
        policy_id=job.policy_id,
        policy_name=job.policy.name if job.policy else "Default Policy",
        status=job.status,
        started_at=job.started_at,
        created_at=job.created_at,
        data_processed_mb=412.0,
        progress_percent=25
    )
    return ApiResponse(success=True, data=res, message="Backup job started successfully")

@router.post("/{job_id}/cancel", response_model=ApiResponse[JobResponse])
def cancel_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "operator"]))
):
    j = find_job(db, job_id)
    j.status = "cancelled"
    j.completed_at = datetime.datetime.now(datetime.timezone.utc)

    # Cancel runs
    for run in j.runs:
        if run.status == "running":
            run.status = "cancelled"
            run.completed_at = j.completed_at

    db.commit()
    db.refresh(j)

    log_audit_event(
        db=db,
        action="JOB_CANCELLED",
        resource_type="job",
        resource_id=j.job_id,
        user_id=current_user.id,
        client_id=j.client_id,
        details=f"Backup job {j.job_id} cancelled by user {current_user.username}"
    )

    res = JobResponse(
        id=j.id,
        job_id=j.job_id,
        client_id=j.client_id,
        client_identifier=j.client.client_id if j.client else f"PC-{j.client_id:03d}",
        client_hostname=j.client.hostname if j.client else f"CLIENT-{j.client_id}",
        policy_id=j.policy_id,
        policy_name=j.policy.name if j.policy else "Default Policy",
        status=j.status,
        started_at=j.started_at,
        completed_at=j.completed_at,
        created_at=j.created_at
    )
    return ApiResponse(success=True, data=res, message="Job cancelled successfully")

@router.post("/{job_id}/retry", response_model=ApiResponse[JobResponse])
def retry_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "operator"]))
):
    j = find_job(db, job_id)
    now = datetime.datetime.now(datetime.timezone.utc)
    j.status = "running"
    j.started_at = now
    j.completed_at = None

    run = BackupRun(
        job_id=j.id,
        client_id=j.client_id,
        backup_type="incremental",
        started_at=now,
        status="running",
        files_processed=10,
        bytes_processed=50 * 1024 * 1024
    )
    db.add(run)
    db.commit()
    db.refresh(j)

    log_audit_event(
        db=db,
        action="JOB_RETRIED",
        resource_type="job",
        resource_id=j.job_id,
        user_id=current_user.id,
        client_id=j.client_id,
        details=f"Retried job {j.job_id}"
    )

    res = JobResponse(
        id=j.id,
        job_id=j.job_id,
        client_id=j.client_id,
        client_identifier=j.client.client_id if j.client else f"PC-{j.client_id:03d}",
        client_hostname=j.client.hostname if j.client else f"CLIENT-{j.client_id}",
        policy_id=j.policy_id,
        policy_name=j.policy.name if j.policy else "Default Policy",
        status=j.status,
        started_at=j.started_at,
        created_at=j.created_at,
        data_processed_mb=50.0,
        progress_percent=15
    )
    return ApiResponse(success=True, data=res, message="Job retry initiated")
