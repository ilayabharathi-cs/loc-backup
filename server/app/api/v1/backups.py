import os
import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Header, Request, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.backup_job import BackupJob
from app.models.backup_run import BackupRun
from app.models.backup_file import BackupFile
from app.models.recovery_point import RecoveryPoint
from app.models.client import Client
from app.models.backup_policy import BackupPolicy
from app.schemas.backup import (
    BackupRunCreate,
    BackupRunProgressUpdate,
    BackupRunCompleteRequest,
    BackupRunResponse,
    RecoveryPointResponse,
    BackupFileResponse,
)
from app.schemas.common import ApiResponse
from app.security.dependencies import get_optional_current_user
from app.services.repository import get_repository
from app.services.audit_service import log_audit_event

router = APIRouter(prefix="/backups", tags=["Backups Data Plane & Telemetry"])


def _to_run_response(r: BackupRun) -> BackupRunResponse:
    return BackupRunResponse(
        id=r.id,
        job_id=r.job_id,
        client_id=r.client_id,
        client_identifier=r.client.client_id if r.client else f"PC-{r.client_id:03d}",
        policy_id=r.policy_id,
        backup_type=r.backup_type,
        started_at=r.started_at,
        completed_at=r.completed_at,
        status=r.status,
        files_processed=r.files_processed,
        files_discovered=r.files_discovered or 0,
        files_uploaded=r.files_uploaded or 0,
        files_failed=r.files_failed or 0,
        bytes_total=r.bytes_total or 0,
        bytes_processed=r.bytes_processed or 0,
        bytes_uploaded=r.bytes_uploaded or 0,
        error_count=r.error_count or 0,
        error_message=r.error_message,
    )


@router.get("/runs", response_model=ApiResponse[List[BackupRunResponse]])
def list_backup_runs(
    client_id: Optional[str] = Query(None, description="Filter by client_id"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user=Depends(get_optional_current_user)
):
    query = db.query(BackupRun)
    if client_id:
        if client_id.isdigit():
            query = query.filter(BackupRun.client_id == int(client_id))
        else:
            client = db.query(Client).filter(Client.client_id == client_id).first()
            if client:
                query = query.filter(BackupRun.client_id == client.id)

    runs = query.order_by(BackupRun.started_at.desc()).limit(limit).all()
    results = [_to_run_response(r) for r in runs]
    return ApiResponse(success=True, data=results, message=f"Retrieved {len(results)} backup runs")


@router.post("/runs", response_model=ApiResponse[BackupRunResponse], status_code=status.HTTP_201_CREATED)
def create_backup_run(request: BackupRunCreate, db: Session = Depends(get_db)):
    """Create and initialize a new backup run."""
    client = None
    if request.client_id.isdigit():
        client = db.query(Client).filter(Client.id == int(request.client_id)).first()
    if not client:
        client = db.query(Client).filter(Client.client_id == request.client_id).first()
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Client '{request.client_id}' not found")

    policy_id = request.policy_id
    if not policy_id:
        policy = db.query(BackupPolicy).filter(BackupPolicy.is_active == True).first()
        policy_id = policy.id if policy else None

    now = datetime.datetime.now(datetime.timezone.utc)
    # Check if there is an active/pending job or create one
    job_count = db.query(BackupJob).count()
    job = BackupJob(
        job_id=f"JOB-{9400 + job_count + 1}",
        client_id=client.id,
        policy_id=policy_id,
        status="running",
        started_at=now
    )
    db.add(job)
    db.flush()

    run = BackupRun(
        job_id=job.id,
        client_id=client.id,
        policy_id=policy_id,
        backup_type=request.backup_type or "full",
        started_at=now,
        status="running",
        files_discovered=request.files_discovered,
        bytes_total=request.bytes_total,
        files_processed=0,
        files_uploaded=0,
        files_failed=0,
        bytes_processed=0,
        bytes_uploaded=0,
    )
    db.add(run)
    client.last_seen = now
    db.commit()
    db.refresh(run)

    log_audit_event(
        db=db,
        action="BACKUP_RUN_STARTED",
        resource_type="backup_run",
        resource_id=str(run.id),
        client_id=client.id,
        details=f"Initial full backup run {run.id} started for {client.client_id} ({request.files_discovered} files)"
    )

    return ApiResponse(success=True, data=_to_run_response(run), message="Backup run initialized successfully")


@router.get("/runs/{run_id}", response_model=ApiResponse[BackupRunResponse])
def get_backup_run(run_id: int, db: Session = Depends(get_db)):
    r = db.query(BackupRun).filter(BackupRun.id == run_id).first()
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup run not found")
    return ApiResponse(success=True, data=_to_run_response(r), message="Backup run details retrieved")


@router.post("/runs/{run_id}/progress", response_model=ApiResponse[BackupRunResponse])
def update_backup_run_progress(run_id: int, progress: BackupRunProgressUpdate, db: Session = Depends(get_db)):
    """Update progress telemetry for a running backup."""
    r = db.query(BackupRun).filter(BackupRun.id == run_id).first()
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup run not found")

    if progress.files_discovered is not None:
        r.files_discovered = progress.files_discovered
    if progress.files_uploaded is not None:
        r.files_uploaded = progress.files_uploaded
        r.files_processed = progress.files_uploaded
    if progress.files_failed is not None:
        r.files_failed = progress.files_failed
    if progress.bytes_total is not None:
        r.bytes_total = progress.bytes_total
    if progress.bytes_uploaded is not None:
        r.bytes_uploaded = progress.bytes_uploaded
        r.bytes_processed = progress.bytes_uploaded
    if progress.error_count is not None:
        r.error_count = progress.error_count
    if progress.error_message:
        r.error_message = progress.error_message

    db.commit()
    db.refresh(r)
    return ApiResponse(success=True, data=_to_run_response(r), message="Progress updated")


@router.post("/upload", response_model=ApiResponse[BackupFileResponse])
async def upload_backup_file(
    request: Request,
    file: Optional[UploadFile] = File(None),
    x_client_id: Optional[str] = Header(None, alias="X-Client-ID"),
    x_run_id: Optional[int] = Header(None, alias="X-Run-ID"),
    x_original_path: Optional[str] = Header(None, alias="X-Original-Path"),
    x_relative_path: Optional[str] = Header(None, alias="X-Relative-Path"),
    x_sha256: Optional[str] = Header(None, alias="X-SHA256"),
    x_file_size: Optional[int] = Header(None, alias="X-File-Size"),
    x_modified_time: Optional[str] = Header(None, alias="X-Modified-Time"),
    # Form data fallback
    client_id: Optional[str] = Form(None),
    run_id: Optional[int] = Form(None),
    original_path: Optional[str] = Form(None),
    relative_path: Optional[str] = Form(None),
    sha256: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Streaming file content upload endpoint.
    Transfers file content into repository object storage and logs file metadata.
    """
    eff_client_id = x_client_id or client_id or request.query_params.get("client_id")
    eff_run_id_val = x_run_id or run_id or request.query_params.get("run_id")
    eff_orig_path = x_original_path or original_path or request.query_params.get("original_path")
    eff_rel_path = x_relative_path or relative_path or request.query_params.get("relative_path")
    eff_sha256 = x_sha256 or sha256 or request.query_params.get("sha256")

    if not eff_client_id or not eff_run_id_val or not eff_orig_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required parameters: client_id, run_id, and original_path are mandatory."
        )

    try:
        eff_run_id = int(eff_run_id_val)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="run_id must be an integer.")

    # 1. Verify Client and BackupRun exist
    run = db.query(BackupRun).filter(BackupRun.id == eff_run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Backup run {eff_run_id} not found.")

    client = db.query(Client).filter(Client.id == run.client_id).first()
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client record not found.")

    # Security: Client isolation check
    if eff_client_id != client.client_id and eff_client_id != str(client.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: Client '{eff_client_id}' does not own run {eff_run_id}."
        )

    repo = get_repository()
    file_name = os.path.basename(eff_orig_path)
    object_id = eff_sha256 or f"obj_{hash(eff_orig_path)}_{os.path.getmtime(eff_orig_path) if os.path.exists(eff_orig_path) else '0'}"

    # Stream content into repository
    try:
        if file is not None:
            rel_storage_path, bytes_written, computed_sha = repo.store_object(
                client_identifier=client.client_id,
                run_id=eff_run_id,
                object_id=object_id,
                content=file.file,
                expected_sha256=eff_sha256
            )
        else:
            # Raw stream
            body = await request.body()
            rel_storage_path, bytes_written, computed_sha = repo.store_object(
                client_identifier=client.client_id,
                run_id=eff_run_id,
                object_id=object_id,
                content=body,
                expected_sha256=eff_sha256
            )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Storage failure: {e}")

    # Parse modified time if provided
    mtime = None
    if x_modified_time:
        try:
            mtime = datetime.datetime.fromisoformat(x_modified_time)
        except Exception:
            pass

    # Record metadata in database
    backup_file = BackupFile(
        client_id=client.id,
        original_path=eff_orig_path,
        relative_path=eff_rel_path,
        file_name=file_name,
        size_bytes=bytes_written,
        sha256=computed_sha,
        version=1,
        backup_run_id=run.id,
        storage_object=rel_storage_path,
        upload_status="completed",
        modified_time=mtime
    )
    db.add(backup_file)

    # Increment telemetry on run
    run.files_uploaded = (run.files_uploaded or 0) + 1
    run.files_processed = (run.files_processed or 0) + 1
    run.bytes_uploaded = (run.bytes_uploaded or 0) + bytes_written
    run.bytes_processed = (run.bytes_processed or 0) + bytes_written
    client.last_seen = datetime.datetime.now(datetime.timezone.utc)

    db.commit()
    db.refresh(backup_file)

    res = BackupFileResponse(
        id=backup_file.id,
        client_id=backup_file.client_id,
        original_path=backup_file.original_path,
        relative_path=backup_file.relative_path,
        file_name=backup_file.file_name,
        size_bytes=backup_file.size_bytes,
        sha256=backup_file.sha256,
        version=backup_file.version,
        backup_run_id=backup_file.backup_run_id,
        storage_object=backup_file.storage_object,
        upload_status=backup_file.upload_status,
        modified_time=backup_file.modified_time,
        created_at=backup_file.created_at
    )
    return ApiResponse(success=True, data=res, message=f"File '{file_name}' uploaded successfully")


@router.post("/runs/{run_id}/complete", response_model=ApiResponse[BackupRunResponse])
def complete_backup_run(run_id: int, request: BackupRunCompleteRequest, db: Session = Depends(get_db)):
    """Finalize a backup run and create a point-in-time Recovery Point upon success."""
    run = db.query(BackupRun).filter(BackupRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Backup run {run_id} not found.")

    now = datetime.datetime.now(datetime.timezone.utc)
    run.completed_at = now
    run.status = request.status
    run.files_uploaded = request.files_uploaded
    run.files_failed = request.files_failed
    run.bytes_uploaded = request.bytes_uploaded
    run.error_count = request.error_count
    if request.error_message:
        run.error_message = request.error_message

    # Update associated job
    if run.job:
        run.job.status = request.status
        run.job.completed_at = now

    # Only create RecoveryPoint if run completed successfully
    recovery_point = None
    if request.status == "completed":
        recovery_point = RecoveryPoint(
            client_id=run.client_id,
            backup_run_id=run.id,
            timestamp=now,
            files_count=request.files_uploaded,
            total_size_bytes=request.bytes_uploaded,
            status="valid",
            created_at=now
        )
        db.add(recovery_point)

        log_audit_event(
            db=db,
            action="BACKUP_RUN_COMPLETED",
            resource_type="backup_run",
            resource_id=str(run.id),
            client_id=run.client_id,
            details=f"Backup run {run.id} completed ({request.files_uploaded} files, {round(request.bytes_uploaded / (1024*1024), 2)} MB). Recovery point created."
        )
    else:
        log_audit_event(
            db=db,
            action="BACKUP_RUN_FAILED",
            resource_type="backup_run",
            resource_id=str(run.id),
            client_id=run.client_id,
            details=f"Backup run {run.id} failed: {request.error_message or 'Errors encountered during upload'}"
        )

    db.commit()
    db.refresh(run)

    return ApiResponse(
        success=True,
        data=_to_run_response(run),
        message=f"Backup run marked {request.status}. Recovery point {'created' if recovery_point else 'skipped'}."
    )


@router.get("/files", response_model=ApiResponse[List[BackupFileResponse]])
def list_backup_files(
    run_id: Optional[int] = Query(None),
    client_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    query = db.query(BackupFile)
    if run_id:
        query = query.filter(BackupFile.backup_run_id == run_id)
    if client_id:
        if client_id.isdigit():
            query = query.filter(BackupFile.client_id == int(client_id))
        else:
            c = db.query(Client).filter(Client.client_id == client_id).first()
            if c:
                query = query.filter(BackupFile.client_id == c.id)

    files = query.order_by(BackupFile.created_at.desc()).limit(limit).all()
    results = [
        BackupFileResponse(
            id=f.id,
            client_id=f.client_id,
            original_path=f.original_path,
            relative_path=f.relative_path,
            file_name=f.file_name,
            size_bytes=f.size_bytes,
            sha256=f.sha256,
            version=f.version,
            backup_run_id=f.backup_run_id,
            storage_object=f.storage_object,
            upload_status=f.upload_status,
            modified_time=f.modified_time,
            created_at=f.created_at
        )
        for f in files
    ]
    return ApiResponse(success=True, data=results, message=f"Retrieved {len(results)} files")


@router.get("/recovery-points", response_model=ApiResponse[List[RecoveryPointResponse]])
def list_recovery_points(
    client_id: Optional[str] = Query(None, description="Filter by client_id"),
    db: Session = Depends(get_db),
    current_user=Depends(get_optional_current_user)
):
    query = db.query(RecoveryPoint)
    if client_id:
        if client_id.isdigit():
            query = query.filter(RecoveryPoint.client_id == int(client_id))
        else:
            client = db.query(Client).filter(Client.client_id == client_id).first()
            if client:
                query = query.filter(RecoveryPoint.client_id == client.id)

    pts = query.order_by(RecoveryPoint.timestamp.desc()).all()
    results = [
        RecoveryPointResponse(
            id=p.id,
            client_id=p.client_id,
            client_identifier=p.client.client_id if p.client else f"PC-{p.client_id:03d}",
            client_hostname=p.client.hostname if p.client else f"CLIENT-{p.client_id}",
            backup_run_id=p.backup_run_id,
            timestamp=p.timestamp,
            files_count=p.files_count,
            total_size_bytes=p.total_size_bytes,
            status=p.status,
            created_at=p.created_at
        )
        for p in pts
    ]
    return ApiResponse(success=True, data=results, message=f"Retrieved {len(results)} recovery points")


@router.get("/recovery-points/{recovery_point_id}", response_model=ApiResponse[RecoveryPointResponse])
def get_recovery_point(recovery_point_id: int, db: Session = Depends(get_db)):
    p = db.query(RecoveryPoint).filter(RecoveryPoint.id == recovery_point_id).first()
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recovery point not found")
    res = RecoveryPointResponse(
        id=p.id,
        client_id=p.client_id,
        client_identifier=p.client.client_id if p.client else f"PC-{p.client_id:03d}",
        client_hostname=p.client.hostname if p.client else f"CLIENT-{p.client_id}",
        backup_run_id=p.backup_run_id,
        timestamp=p.timestamp,
        files_count=p.files_count,
        total_size_bytes=p.total_size_bytes,
        status=p.status,
        created_at=p.created_at
    )
    return ApiResponse(success=True, data=res, message="Recovery point details retrieved")
