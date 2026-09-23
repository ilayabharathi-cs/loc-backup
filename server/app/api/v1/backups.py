import os
import uuid
import hashlib
import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Header, Request, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.backup_job import BackupJob
from app.models.backup_run import BackupRun
from app.models.backup_file import BackupFile
from app.models.recovery_point import RecoveryPoint
from app.models.storage_object import StorageObject
from app.models.client import Client
from app.models.backup_policy import BackupPolicy
from app.models.upload_session import UploadSession
from app.models.upload_chunk import UploadChunk
from app.models.backup_checkpoint import BackupCheckpoint
from app.models.run_event import RunEvent
from app.schemas.backup import (
    BackupRunCreate,
    BackupRunProgressUpdate,
    BackupRunCompleteRequest,
    BackupRunResponse,
    RecoveryPointResponse,
    BackupFileResponse,
    BatchFileMetadataRequest,
    RecoveryPointManifestResponse,
    ManifestFileEntry,
    UploadSessionCreateRequest,
    UploadSessionResponse,
    UploadSessionStatusResponse,
    ChunkUploadResponse,
    UploadSessionCompleteRequest,
    RunStateUpdateRequest,
    RunStateResponse,
    RunCheckpointRequest,
    RunCheckpointResponse,
    RunLeaseRenewRequest,
    RunLeaseRenewResponse,
    RunEventResponse,
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
        backup_type=r.backup_type or "full",
        baseline_run_id=r.baseline_run_id,
        started_at=r.started_at,
        completed_at=r.completed_at,
        status=r.status,
        state=r.state or "CREATED",
        lease_id=r.lease_id,
        lease_expires_at=r.lease_expires_at,
        interrupted_at=r.interrupted_at,
        resumed_at=r.resumed_at,
        checkpoint_version=r.checkpoint_version or 1,
        retry_count=r.retry_count or 0,
        files_locked=r.files_locked or 0,
        files_vss_recovered=r.files_vss_recovered or 0,
        files_skipped=r.files_skipped or 0,
        files_processed=r.files_processed,
        files_discovered=r.files_discovered or 0,
        files_uploaded=r.files_uploaded or 0,
        files_failed=r.files_failed or 0,
        files_new=r.files_new or 0,
        files_modified=r.files_modified or 0,
        files_unchanged=r.files_unchanged or 0,
        files_deleted=r.files_deleted or 0,
        bytes_total=r.bytes_total or 0,
        bytes_processed=r.bytes_processed or 0,
        bytes_uploaded=r.bytes_uploaded or 0,
        error_count=r.error_count or 0,
        error_message=r.error_message,
    )


def _to_file_response(f: BackupFile) -> BackupFileResponse:
    return BackupFileResponse(
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
        storage_object_id=getattr(f, "storage_object_id", None),
        upload_status=f.upload_status,
        change_type=f.change_type or "FULL",
        modified_time=f.modified_time,
        created_at=f.created_at
    )


def _to_point_response(p: RecoveryPoint) -> RecoveryPointResponse:
    return RecoveryPointResponse(
        id=p.id,
        client_id=p.client_id,
        client_identifier=p.client.client_id if p.client else f"PC-{p.client_id:03d}",
        client_hostname=p.client.hostname if p.client else f"CLIENT-{p.client_id}",
        backup_run_id=p.backup_run_id,
        backup_type=p.backup_type or (p.run.backup_type if p.run else "full"),
        timestamp=p.timestamp,
        files_count=p.files_count,
        total_size_bytes=p.total_size_bytes,
        status=p.status,
        created_at=p.created_at,
        retention_status=getattr(p, "retention_status", "active") or "active",
        is_daily=getattr(p, "is_daily", False) or False,
        is_weekly=getattr(p, "is_weekly", False) or False,
        is_monthly=getattr(p, "is_monthly", False) or False,
        is_yearly=getattr(p, "is_yearly", False) or False,
        is_manual_protected=getattr(p, "is_manual_protected", False) or False,
        expires_at=getattr(p, "expires_at", None),
        retention_tier=getattr(p, "retention_tier", None),
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
    """Create and initialize a new backup run (Full or Incremental)."""
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

    eff_type = (request.backup_type or "full").lower()
    now = datetime.datetime.now(datetime.timezone.utc)

    # Phase 14: Safe Concurrency - Enforce single active backup run per client + policy
    # Prevents simultaneous FULL + INCREMENTAL runs, or any concurrent run if prevent_concurrent is requested
    conflicting_query = db.query(BackupRun).filter(
        BackupRun.client_id == client.id,
        BackupRun.policy_id == policy_id,
        BackupRun.status == "running",
        BackupRun.state.notin_(["COMPLETED", "FAILED", "CANCELLED"])
    )
    if request.prevent_concurrent:
        conflicting_run = conflicting_query.first()
    else:
        conflicting_run = conflicting_query.filter(BackupRun.backup_type != eff_type).first()

    if conflicting_run:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An active backup run (ID {conflicting_run.id}, type: {conflicting_run.backup_type}, state: {conflicting_run.state}) already exists for client '{client.client_id}' and policy '{policy_id}'. Simultaneous runs are prohibited."
        )

    # Check if there is an active/pending job or create one
    job_count = db.query(BackupJob).count()
    job = BackupJob(
        job_id=f"JOB-{9400 + job_count + 1}",
        client_id=client.id,
        policy_id=policy_id,
        backup_type=eff_type,
        status="running",
        started_at=now
    )
    db.add(job)
    db.flush()

    # Phase 13: Issue 5-minute renewable run lease
    lease_id = str(uuid.uuid4())
    lease_expiry = now + datetime.timedelta(seconds=300)

    run = BackupRun(
        job_id=job.id,
        client_id=client.id,
        policy_id=policy_id,
        backup_type=eff_type,
        baseline_run_id=request.baseline_run_id,
        started_at=now,
        status="running",
        state="CREATED",
        lease_id=lease_id,
        lease_expires_at=lease_expiry,
        checkpoint_version=1,
        retry_count=0,
        files_locked=0,
        files_vss_recovered=0,
        files_skipped=0,
        files_discovered=request.files_discovered,
        bytes_total=request.bytes_total,
        files_processed=0,
        files_uploaded=0,
        files_failed=0,
        files_new=0,
        files_modified=0,
        files_unchanged=0,
        files_deleted=0,
        bytes_processed=0,
        bytes_uploaded=0,
    )
    db.add(run)
    client.last_seen = now

    event = RunEvent(
        run_id=job.id,  # Will link to run after commit
        event_type="BACKUP_STARTED",
        message=f"Backup run ({eff_type.upper()}) created for {client.client_id} with lease {lease_id}"
    )
    db.flush()
    event.run_id = run.id
    db.add(event)

    db.commit()
    db.refresh(run)

    log_audit_event(
        db=db,
        action="BACKUP_RUN_STARTED",
        resource_type="backup_run",
        resource_id=str(run.id),
        client_id=client.id,
        details=f"Backup run {run.id} ({eff_type.upper()}) started for {client.client_id} ({request.files_discovered} files discovered)"
    )

    return ApiResponse(success=True, data=_to_run_response(run), message=f"Backup run ({eff_type}) initialized successfully")


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
    if progress.files_new is not None:
        r.files_new = progress.files_new
    if progress.files_modified is not None:
        r.files_modified = progress.files_modified
    if progress.files_unchanged is not None:
        r.files_unchanged = progress.files_unchanged
    if progress.files_deleted is not None:
        r.files_deleted = progress.files_deleted
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
    x_change_type: Optional[str] = Header(None, alias="X-Change-Type"),
    # Form data fallback
    client_id: Optional[str] = Form(None),
    run_id: Optional[int] = Form(None),
    original_path: Optional[str] = Form(None),
    relative_path: Optional[str] = Form(None),
    sha256: Optional[str] = Form(None),
    change_type: Optional[str] = Form(None),
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
    eff_change_type_val = x_change_type or change_type or request.query_params.get("change_type")

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

    resolved_change_type = eff_change_type_val.upper() if eff_change_type_val else ("FULL" if run.backup_type == "full" else "NEW")

    # V5 Content-Addressed Storage & Deduplication Integration
    storage_obj = db.query(StorageObject).filter(
        StorageObject.content_sha256 == computed_sha
    ).first()

    if storage_obj:
        storage_obj.reference_count += 1
        storage_obj.state = "AVAILABLE"
    else:
        local_physical = repo.resolve_stored_path(rel_storage_path)
        cas_rel, stored_size, stored_sha, comp_algo, comp_ratio = repo.store_cas_object(
            source_path_or_bytes=local_physical,
            content_sha256=computed_sha,
            original_size=bytes_written,
            filename_hint=file_name,
            compress=True,
        )
        storage_obj = StorageObject(
            object_id=f"obj_{computed_sha[:16]}",
            content_sha256=computed_sha,
            stored_sha256=stored_sha,
            original_size=bytes_written,
            stored_size=stored_size,
            compression_algorithm=comp_algo,
            compression_ratio=comp_ratio,
            storage_path=cas_rel,
            reference_count=1,
            state="AVAILABLE",
            integrity_status="VALID",
        )
        db.add(storage_obj)
        db.flush()

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
        storage_object_id=storage_obj.id if storage_obj else None,
        upload_status="completed",
        change_type=resolved_change_type,
        modified_time=mtime
    )
    db.add(backup_file)

    # Increment telemetry on run
    run.files_uploaded = (run.files_uploaded or 0) + 1
    run.files_processed = (run.files_processed or 0) + 1
    run.bytes_uploaded = (run.bytes_uploaded or 0) + bytes_written
    run.bytes_processed = (run.bytes_processed or 0) + bytes_written
    if resolved_change_type == "MODIFIED":
        run.files_modified = (run.files_modified or 0) + 1
    elif resolved_change_type in ("NEW", "FULL"):
        run.files_new = (run.files_new or 0) + 1

    client.last_seen = datetime.datetime.now(datetime.timezone.utc)

    db.commit()
    db.refresh(backup_file)

    return ApiResponse(success=True, data=_to_file_response(backup_file), message=f"File '{file_name}' uploaded successfully")


@router.post("/runs/{run_id}/record-metadata", response_model=ApiResponse[List[BackupFileResponse]])
def record_run_metadata(
    run_id: int,
    request: BatchFileMetadataRequest,
    x_client_id: Optional[str] = Header(None, alias="X-Client-ID"),
    db: Session = Depends(get_db)
):
    """
    Batch register file metadata without transferring data over network.
    Used for UNCHANGED files (referencing previous immutable storage object)
    and DELETED files (tombstone records).
    """
    run = db.query(BackupRun).filter(BackupRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Backup run {run_id} not found.")

    client = db.query(Client).filter(Client.id == run.client_id).first()
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found.")

    if x_client_id and x_client_id != client.client_id and x_client_id != str(client.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    created_records: List[BackupFile] = []
    for item in request.files:
        ct = (item.change_type or "UNCHANGED").upper()
        up_status = "deleted" if ct == "DELETED" else (item.upload_status or "completed")
        storage_obj = None if ct == "DELETED" else item.storage_object

        so_record = None
        if ct != "DELETED" and item.sha256:
            so_record = db.query(StorageObject).filter(
                StorageObject.content_sha256 == item.sha256,
                StorageObject.state == "AVAILABLE"
            ).first()
            if so_record:
                so_record.reference_count += 1

        bf = BackupFile(
            client_id=client.id,
            original_path=item.original_path,
            relative_path=item.relative_path,
            file_name=item.file_name,
            size_bytes=item.size_bytes or 0,
            sha256=item.sha256,
            version=1,
            backup_run_id=run.id,
            storage_object=storage_obj,
            storage_object_id=so_record.id if so_record else None,
            upload_status=up_status,
            change_type=ct,
            modified_time=item.modified_time
        )
        db.add(bf)
        created_records.append(bf)

        if ct == "UNCHANGED":
            run.files_unchanged = (run.files_unchanged or 0) + 1
        elif ct == "DELETED":
            run.files_deleted = (run.files_deleted or 0) + 1

    db.commit()
    for r in created_records:
        db.refresh(r)

    results = [_to_file_response(r) for r in created_records]
    return ApiResponse(success=True, data=results, message=f"Recorded {len(results)} file metadata records")


@router.post("/runs/{run_id}/complete", response_model=ApiResponse[BackupRunResponse])
def complete_backup_run(run_id: int, request: BackupRunCompleteRequest, db: Session = Depends(get_db)):
    """
    Finalize a backup run with ATOMIC snapshot consistency validation.
    Verifies all 7 validation criteria before creating a valid Recovery Point:
    1. All NEW files have successful metadata/object records.
    2. All MODIFIED files have successful object records.
    3. All UNCHANGED files reference a valid previous storage object.
    4. All DELETED files have valid tombstone metadata.
    5. No required file is missing from the logical manifest.
    6. No upload is still pending.
    7. No file is marked FAILED or CHANGED_DURING_BACKUP.
    """
    run = db.query(BackupRun).filter(BackupRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Backup run {run_id} not found.")

    now = datetime.datetime.now(datetime.timezone.utc)
    run.completed_at = now
    run.files_uploaded = request.files_uploaded
    run.files_failed = request.files_failed
    run.bytes_uploaded = request.bytes_uploaded
    if request.files_discovered is not None:
        run.files_discovered = request.files_discovered
    if request.bytes_total is not None:
        run.bytes_total = request.bytes_total
    if request.files_new:
        run.files_new = request.files_new
    if request.files_modified:
        run.files_modified = request.files_modified
    if request.files_unchanged:
        run.files_unchanged = request.files_unchanged
    if request.files_deleted:
        run.files_deleted = request.files_deleted
    run.error_count = request.error_count
    if request.error_message:
        run.error_message = request.error_message

    # Load all registered files for this run
    recorded_files = db.query(BackupFile).filter(BackupFile.backup_run_id == run.id).all()

    # --- EXPANDED 12-RULE ATOMIC RECOVERY POINT VALIDATION ENGINE ---
    validation_passed = True
    validation_errors: List[str] = []

    if request.status != "completed":
        validation_passed = False
        validation_errors.append(f"Run requested with non-completed status '{request.status}'.")

    if request.files_failed > 0:
        validation_passed = False
        validation_errors.append(f"{request.files_failed} files failed or were locked during backup.")

    # Rule 6: Check for incomplete/active upload sessions
    active_sessions = db.query(UploadSession).filter(
        UploadSession.run_id == run.id,
        UploadSession.status == "active"
    ).all()
    if active_sessions:
        validation_passed = False
        validation_errors.append(f"{len(active_sessions)} upload sessions remain active/incomplete.")

    for f in recorded_files:
        ct = (f.change_type or "").upper()
        # Rule 1: NEW / FULL files check
        if ct in ("NEW", "FULL"):
            if f.upload_status != "completed" or not f.storage_object:
                validation_passed = False
                validation_errors.append(f"NEW file '{f.file_name}' incomplete (status={f.upload_status}, storage_object={f.storage_object}).")

        # Rule 2: MODIFIED files check
        elif ct == "MODIFIED":
            if f.upload_status != "completed" or not f.storage_object:
                validation_passed = False
                validation_errors.append(f"MODIFIED file '{f.file_name}' incomplete (status={f.upload_status}, storage_object={f.storage_object}).")

        # Rule 3: UNCHANGED files check
        elif ct == "UNCHANGED":
            if f.upload_status != "completed" or not f.storage_object:
                validation_passed = False
                validation_errors.append(f"UNCHANGED file '{f.file_name}' missing valid object reference.")

        # Rule 4: DELETED files check
        elif ct == "DELETED":
            if f.upload_status != "deleted" or f.storage_object is not None:
                validation_passed = False
                validation_errors.append(f"DELETED file '{f.file_name}' has invalid tombstone metadata.")

        # Rule 6b: No upload pending
        if f.upload_status in ("pending", "uploading"):
            validation_passed = False
            validation_errors.append(f"File '{f.file_name}' is still in pending upload state.")

        # Rule 7 & 8: No file marked failed or changed_during_backup
        if f.upload_status in ("failed", "changed_during_backup", "locked"):
            validation_passed = False
            validation_errors.append(f"File '{f.file_name}' marked '{f.upload_status}'.")

        # Rule 9 & 10: Valid checksum and non-negative size for active files
        if ct != "DELETED" and f.upload_status == "completed":
            if not f.sha256 or not f.sha256.strip():
                validation_passed = False
                validation_errors.append(f"File '{f.file_name}' missing valid SHA-256 checksum.")
            if f.size_bytes < 0:
                validation_passed = False
                validation_errors.append(f"File '{f.file_name}' has negative size {f.size_bytes}.")

    # Rule 5: Missing files check against baseline
    if run.backup_type == "incremental" and run.baseline_run_id:
        baseline_active = db.query(BackupFile).filter(
            BackupFile.backup_run_id == run.baseline_run_id,
            BackupFile.change_type != "DELETED",
            BackupFile.upload_status == "completed"
        ).all()
        current_rel_paths = {f.relative_path or f.original_path for f in recorded_files}
        missing_paths = [
            b.relative_path or b.original_path
            for b in baseline_active
            if (b.relative_path or b.original_path) not in current_rel_paths
        ]
        if missing_paths:
            validation_passed = False
            validation_errors.append(
                f"{len(missing_paths)} baseline files missing from logical snapshot (e.g., '{missing_paths[0]}')."
            )

    # Determine final run status and state
    if validation_passed and request.status == "completed":
        final_status = "completed"
        final_state = "COMPLETED"
    elif request.files_failed > 0 or not validation_passed:
        final_status = "completed_with_warnings" if (request.files_uploaded > 0) else "failed"
        final_state = "FAILED"
    else:
        final_status = request.status
        final_state = "FAILED" if request.status == "failed" else "COMPLETED"

    run.status = final_status
    run.state = final_state
    if not validation_passed and validation_errors:
        err_str = "; ".join(validation_errors[:5])
        run.error_message = f"Validation failed: {err_str}"

    # Update associated job
    if run.job:
        run.job.status = final_status
        run.job.completed_at = now

    # Atomic Recovery Point creation: strictly only created if ALL validation checks pass!
    recovery_point = None
    if validation_passed and final_status == "completed":
        active_files = [f for f in recorded_files if (f.change_type or "").upper() != "DELETED"]
        eff_files_count = len(active_files) if recorded_files else request.files_uploaded
        eff_total_size = sum(f.size_bytes for f in active_files) if recorded_files else request.bytes_uploaded

        recovery_point = RecoveryPoint(
            client_id=run.client_id,
            backup_run_id=run.id,
            backup_type=run.backup_type or "full",
            timestamp=now,
            files_count=eff_files_count,
            total_size_bytes=eff_total_size,
            status="valid",
            retention_status="active",
            retention_tier="NEWEST",
            created_at=now
        )
        db.add(recovery_point)

        # Log structured run event
        event = RunEvent(
            run_id=run.id,
            event_type="BACKUP_COMPLETED",
            message=f"Backup run {run.id} verified and completed. Recovery point created."
        )
        db.add(event)

        log_audit_event(
            db=db,
            action="BACKUP_RUN_COMPLETED",
            resource_type="backup_run",
            resource_id=str(run.id),
            client_id=run.client_id,
            details=(
                f"Backup run {run.id} ({run.backup_type}) completed. "
                f"Active snapshot: {len(active_files)} files, {round(eff_total_size / (1024*1024), 2)} MB. "
                f"Uploaded: {request.files_uploaded} files. Recovery point created."
            )
        )
    else:
        event = RunEvent(
            run_id=run.id,
            event_type="BACKUP_FAILED",
            message=f"Backup run {run.id} failed validation: {run.error_message}"
        )
        db.add(event)

        log_audit_event(
            db=db,
            action="BACKUP_RUN_FAILED" if final_status == "failed" else "BACKUP_RUN_WARNING",
            resource_type="backup_run",
            resource_id=str(run.id),
            client_id=run.client_id,
            details=f"Backup run {run.id} finished with status '{final_status}'. Recovery point skipped: {run.error_message}"
        )

    db.commit()
    db.refresh(run)

    return ApiResponse(
        success=True,
        data=_to_run_response(run),
        message=(
            f"Backup run marked {final_status}. "
            f"Recovery point {'created' if recovery_point else 'skipped: ' + (run.error_message or 'validation criteria not met')}."
        )
    )


@router.get("/files", response_model=ApiResponse[List[BackupFileResponse]])
def list_backup_files(
    run_id: Optional[int] = Query(None),
    client_id: Optional[str] = Query(None),
    limit: int = Query(500, ge=1, le=10000),
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
    results = [_to_file_response(f) for f in files]
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
    results = [_to_point_response(p) for p in pts]
    return ApiResponse(success=True, data=results, message=f"Retrieved {len(results)} recovery points")


@router.get("/recovery-points/latest", response_model=ApiResponse[Optional[RecoveryPointResponse]])
def get_latest_recovery_point(
    client_id: str = Query(..., description="Client identifier"),
    policy_id: Optional[int] = Query(None, description="Optional policy filter"),
    db: Session = Depends(get_db)
):
    """
    Find latest valid completed Recovery Point for baseline comparison.
    Rejects incomplete, failed, or corrupted recovery points.
    """
    client = None
    if client_id.isdigit():
        client = db.query(Client).filter(Client.id == int(client_id)).first()
    if not client:
        client = db.query(Client).filter(Client.client_id == client_id).first()
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Client '{client_id}' not found")

    query = db.query(RecoveryPoint).join(BackupRun, RecoveryPoint.backup_run_id == BackupRun.id).filter(
        RecoveryPoint.client_id == client.id,
        RecoveryPoint.status == "valid",
        BackupRun.status == "completed"
    )

    if policy_id is not None:
        query = query.filter(BackupRun.policy_id == policy_id)

    latest_rp = query.order_by(RecoveryPoint.timestamp.desc()).first()
    if not latest_rp:
        return ApiResponse(success=True, data=None, message="No valid completed baseline recovery point found.")

    res = _to_point_response(latest_rp)
    return ApiResponse(success=True, data=res, message="Latest baseline recovery point retrieved")


@router.get("/recovery-points/{recovery_point_id}", response_model=ApiResponse[RecoveryPointResponse])
def get_recovery_point(recovery_point_id: int, db: Session = Depends(get_db)):
    p = db.query(RecoveryPoint).filter(RecoveryPoint.id == recovery_point_id).first()
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recovery point not found")
    res = _to_point_response(p)
    return ApiResponse(success=True, data=res, message="Recovery point details retrieved")


@router.get("/recovery-points/{recovery_point_id}/manifest", response_model=ApiResponse[RecoveryPointManifestResponse])
def get_recovery_point_manifest(
    recovery_point_id: int,
    include_deleted: bool = Query(False, description="Include tombstoned deleted files"),
    db: Session = Depends(get_db)
):
    """
    Retrieve the complete logical file manifest for a given Recovery Point.
    Enables future restore operations to reconstruct the exact filesystem snapshot.
    """
    rp = db.query(RecoveryPoint).filter(RecoveryPoint.id == recovery_point_id).first()
    if not rp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recovery point not found")

    query = db.query(BackupFile).filter(BackupFile.backup_run_id == rp.backup_run_id)
    if not include_deleted:
        query = query.filter(BackupFile.change_type != "DELETED")

    files = query.all()
    entries = [
        ManifestFileEntry(
            id=f.id,
            file_name=f.file_name,
            original_path=f.original_path,
            relative_path=f.relative_path,
            size_bytes=f.size_bytes,
            sha256=f.sha256,
            storage_object=f.storage_object,
            change_type=f.change_type or "FULL",
            upload_status=f.upload_status,
            modified_time=f.modified_time,
            created_at=f.created_at
        )
        for f in files
    ]

    manifest = RecoveryPointManifestResponse(
        recovery_point_id=rp.id,
        backup_run_id=rp.backup_run_id,
        client_id=rp.client_id,
        backup_type=rp.backup_type or (rp.run.backup_type if rp.run else "full"),
        total_files=len(entries),
        total_size_bytes=sum(e.size_bytes for e in entries if e.change_type != "DELETED"),
        timestamp=rp.timestamp,
        files=entries
    )
    return ApiResponse(success=True, data=manifest, message=f"Manifest retrieved ({len(entries)} files)")


@router.get("/recovery-points/{recovery_point_id}/files", response_model=ApiResponse[dict])
def browse_recovery_point_files_tree(
    recovery_point_id: int,
    db: Session = Depends(get_db)
):
    """Browse the virtual directory tree of a Recovery Point."""
    from app.services.restore.planner import RestorePlanner
    rp = db.query(RecoveryPoint).filter(RecoveryPoint.id == recovery_point_id).first()
    if not rp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recovery point not found")

    files = RestorePlanner.get_recovery_point_logical_files(db, rp.id)
    tree = RestorePlanner.build_virtual_tree(files)
    return ApiResponse(success=True, data=tree, message=f"Virtual directory tree retrieved for RP #{rp.id}")


@router.get("/recovery-points/{recovery_point_id}/files/search", response_model=ApiResponse[list])
def search_recovery_point_files_list(
    recovery_point_id: int,
    q: Optional[str] = Query(None, description="Search keyword"),
    ext: Optional[str] = Query(None, description="Filter by extension"),
    db: Session = Depends(get_db)
):
    """Search and filter files inside a Recovery Point."""
    from app.services.restore.planner import RestorePlanner
    rp = db.query(RecoveryPoint).filter(RecoveryPoint.id == recovery_point_id).first()
    if not rp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recovery point not found")

    files = RestorePlanner.get_recovery_point_logical_files(db, rp.id)
    filtered = RestorePlanner.filter_files(files, restore_mode="FULL_RECOVERY_POINT", search_query=q, extension=ext)
    results = [
        {
            "id": f.id,
            "file_name": f.file_name,
            "relative_path": f.relative_path or os.path.basename(f.original_path),
            "original_path": f.original_path,
            "size_bytes": f.size_bytes or 0,
            "sha256": f.sha256,
            "change_type": f.change_type,
            "modified_time": f.modified_time.isoformat() if f.modified_time else None
        }
        for f in filtered
    ]
    return ApiResponse(success=True, data=results, message=f"Found {len(results)} files")


# =============================================================================
# V4 RESUMABLE CHUNKED UPLOADS & RUN RELIABILITY LIFECYCLE
# =============================================================================

@router.post("/runs/{run_id}/upload-session", response_model=ApiResponse[UploadSessionResponse], status_code=status.HTTP_201_CREATED)
def create_upload_session(
    run_id: int,
    req: UploadSessionCreateRequest,
    db: Session = Depends(get_db)
):
    """
    Initiate or retrieve a resumable chunked upload session for a file.
    The server acts as the authoritative record of persisted chunks.
    """
    run = db.query(BackupRun).filter(BackupRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Backup run {run_id} not found")

    client_identifier = run.client.client_id if run.client else f"PC-{run.client_id:03d}"

    # Check if an existing active upload session already exists for this file
    existing = db.query(UploadSession).filter(
        UploadSession.run_id == run.id,
        UploadSession.file_path == req.file_path,
        UploadSession.status == "active"
    ).first()
    if existing:
        return ApiResponse(
            success=True,
            data=UploadSessionResponse(
                upload_session_id=existing.id,
                run_id=existing.run_id,
                object_id=existing.object_id,
                chunk_size=existing.chunk_size,
                total_chunks=existing.total_chunks,
                next_chunk_index=existing.next_chunk_index,
                received_bytes=existing.received_bytes,
                status=existing.status
            ),
            message="Existing active upload session retrieved"
        )

    session_id = str(uuid.uuid4())
    chunk_size = req.chunk_size if req.chunk_size > 0 else 4194304
    total_size = max(0, req.total_size)
    total_chunks = (total_size + chunk_size - 1) // chunk_size if total_size > 0 else 1
    object_id = req.expected_sha256 or f"obj_{session_id}"

    repo = get_repository()
    staging_file = repo.get_staging_path(client_identifier, run.id, session_id)

    session = UploadSession(
        id=session_id,
        run_id=run.id,
        object_id=object_id,
        file_path=req.file_path,
        relative_path=req.relative_path,
        change_type=req.change_type,
        total_size=total_size,
        chunk_size=chunk_size,
        total_chunks=total_chunks,
        received_bytes=0,
        next_chunk_index=0,
        file_mtime=req.file_mtime,
        expected_sha256=req.expected_sha256,
        status="active",
        staging_path=staging_file
    )
    db.add(session)

    event = RunEvent(
        run_id=run.id,
        event_type="UPLOAD_STARTED",
        message=f"Upload session created for '{os.path.basename(req.file_path)}' ({total_size} bytes, {total_chunks} chunks)"
    )
    db.add(event)
    db.commit()
    db.refresh(session)

    return ApiResponse(
        success=True,
        data=UploadSessionResponse(
            upload_session_id=session.id,
            run_id=session.run_id,
            object_id=session.object_id,
            chunk_size=session.chunk_size,
            total_chunks=session.total_chunks,
            next_chunk_index=session.next_chunk_index,
            received_bytes=session.received_bytes,
            status=session.status
        ),
        message="Upload session created"
    )


@router.get("/upload-session/{session_id}", response_model=ApiResponse[UploadSessionStatusResponse])
@router.get("/upload-session/{session_id}/status", response_model=ApiResponse[UploadSessionStatusResponse])
def get_upload_session_status(session_id: str, db: Session = Depends(get_db)):
    """Server is the single source of truth for persisted chunks."""
    session = db.query(UploadSession).filter(UploadSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Upload session {session_id} not found")

    received_chunks = [c.chunk_index for c in session.chunks if c.status == "persisted"]
    return ApiResponse(
        success=True,
        data=UploadSessionStatusResponse(
            upload_session_id=session.id,
            status=session.status,
            total_chunks=session.total_chunks,
            received_bytes=session.received_bytes,
            total_size=session.total_size,
            next_chunk_index=session.next_chunk_index,
            received_chunks=received_chunks
        ),
        message="Upload session status retrieved"
    )


@router.put("/upload-session/{session_id}/chunks/{chunk_index}", response_model=ApiResponse[ChunkUploadResponse])
async def upload_chunk(
    session_id: str,
    chunk_index: int,
    request: Request,
    x_chunk_sha256: str = Header(..., alias="X-Chunk-SHA256"),
    x_chunk_offset: Optional[int] = Header(None, alias="X-Chunk-Offset"),
    db: Session = Depends(get_db)
):
    """
    Idempotent chunk ingestion with SHA-256 integrity validation.
    Duplicate chunk submissions return 200 without appending duplicate data.
    """
    session = db.query(UploadSession).filter(UploadSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Upload session {session_id} not found")
    if session.status != "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Upload session is {session.status}")

    chunk_bytes = await request.body()
    calc_sha256 = hashlib.sha256(chunk_bytes).hexdigest()

    if x_chunk_sha256.lower() != calc_sha256.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chunk checksum mismatch: expected {x_chunk_sha256}, calculated {calc_sha256}"
        )

    # Idempotency: verify if already stored
    existing_chunk = db.query(UploadChunk).filter(
        UploadChunk.upload_session_id == session.id,
        UploadChunk.chunk_index == chunk_index
    ).first()
    if existing_chunk:
        if existing_chunk.sha256.lower() == calc_sha256.lower():
            return ApiResponse(
                success=True,
                data=ChunkUploadResponse(
                    upload_session_id=session.id,
                    chunk_index=chunk_index,
                    offset=existing_chunk.offset,
                    size=existing_chunk.size,
                    sha256=existing_chunk.sha256,
                    status=existing_chunk.status,
                    already_existed=True
                ),
                message="Chunk already acknowledged (idempotent)"
            )

    offset = x_chunk_offset if x_chunk_offset is not None else (chunk_index * session.chunk_size)
    run = session.run
    client_identifier = run.client.client_id if run.client else f"PC-{run.client_id:03d}"

    repo = get_repository()
    repo.write_staging_chunk(client_identifier, run.id, session.id, offset, chunk_bytes)

    if not existing_chunk:
        chunk_rec = UploadChunk(
            upload_session_id=session.id,
            chunk_index=chunk_index,
            offset=offset,
            size=len(chunk_bytes),
            sha256=calc_sha256,
            status="persisted"
        )
        db.add(chunk_rec)
    else:
        existing_chunk.sha256 = calc_sha256
        existing_chunk.size = len(chunk_bytes)
        existing_chunk.status = "persisted"

    # Compute updated session received bytes
    db.flush()
    persisted_chunks = db.query(UploadChunk).filter(
        UploadChunk.upload_session_id == session.id,
        UploadChunk.status == "persisted"
    ).all()
    session.received_bytes = sum(c.size for c in persisted_chunks)
    session.next_chunk_index = max(c.chunk_index for c in persisted_chunks) + 1 if persisted_chunks else 0
    db.commit()

    return ApiResponse(
        success=True,
        data=ChunkUploadResponse(
            upload_session_id=session.id,
            chunk_index=chunk_index,
            offset=offset,
            size=len(chunk_bytes),
            sha256=calc_sha256,
            status="persisted",
            already_existed=False
        ),
        message=f"Chunk {chunk_index} persisted successfully"
    )


@router.post("/upload-session/{session_id}/complete", response_model=ApiResponse[BackupFileResponse])
def complete_upload_session(
    session_id: str,
    req: UploadSessionCompleteRequest,
    db: Session = Depends(get_db)
):
    """
    Finalize chunk assembly, verify whole-file SHA-256 and total size,
    and atomically transition staging data into an immutable repository object.
    """
    session = db.query(UploadSession).filter(UploadSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Upload session {session_id} not found")
    if session.status == "completed":
        f = db.query(BackupFile).filter(
            BackupFile.backup_run_id == session.run_id,
            BackupFile.original_path == session.file_path
        ).first()
        if f:
            return ApiResponse(success=True, data=_to_file_response(f), message="Upload session already completed")

    run = session.run
    client_identifier = run.client.client_id if run.client else f"PC-{run.client_id:03d}"

    repo = get_repository()
    try:
        storage_object_rel, total_bytes, computed_sha256 = repo.finalize_staging_object(
            client_identifier=client_identifier,
            run_id=run.id,
            session_id=session.id,
            object_id=req.final_sha256,
            expected_sha256=req.final_sha256
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Session completion failed: {e}")

    now = datetime.datetime.now(datetime.timezone.utc)
    session.status = "completed"
    session.completed_at = now
    session.final_sha256 = computed_sha256
    session.received_bytes = total_bytes

    # V5 Content-Addressed Storage & Deduplication Integration
    storage_obj = db.query(StorageObject).filter(
        StorageObject.content_sha256 == computed_sha256
    ).first()

    if storage_obj:
        storage_obj.reference_count += 1
        storage_obj.state = "AVAILABLE"
    else:
        staging_file = repo.get_staging_path(client_identifier, run.id, session.id)
        if os.path.exists(staging_file):
            cas_rel, stored_size, stored_sha, comp_algo, comp_ratio = repo.finalize_staging_cas_object(
                staging_file=staging_file,
                content_sha256=computed_sha256,
                original_size=total_bytes,
                filename_hint=session.file_path,
                compress=True,
            )
        else:
            local_physical = repo.resolve_stored_path(storage_object_rel)
            cas_rel, stored_size, stored_sha, comp_algo, comp_ratio = repo.store_cas_object(
                source_path_or_bytes=local_physical,
                content_sha256=computed_sha256,
                original_size=total_bytes,
                filename_hint=session.file_path,
                compress=True,
            )
        storage_obj = StorageObject(
            object_id=f"obj_{computed_sha256[:16]}",
            content_sha256=computed_sha256,
            stored_sha256=stored_sha,
            original_size=total_bytes,
            stored_size=stored_size,
            compression_algorithm=comp_algo,
            compression_ratio=comp_ratio,
            storage_path=cas_rel,
            reference_count=1,
            state="AVAILABLE",
            integrity_status="VALID",
        )
        db.add(storage_obj)
        db.flush()

    f = db.query(BackupFile).filter(
        BackupFile.backup_run_id == run.id,
        BackupFile.original_path == session.file_path
    ).first()

    if not f:
        f = BackupFile(
            client_id=run.client_id,
            backup_run_id=run.id,
            original_path=session.file_path,
            relative_path=session.relative_path,
            file_name=os.path.basename(session.file_path),
            size_bytes=total_bytes,
            sha256=computed_sha256,
            storage_object=storage_object_rel,
            storage_object_id=storage_obj.id if storage_obj else None,
            upload_status="completed",
            change_type=session.change_type,
            modified_time=session.file_mtime,
            version=1
        )
        db.add(f)
    else:
        f.size_bytes = total_bytes
        f.sha256 = computed_sha256
        f.storage_object = storage_object_rel
        f.storage_object_id = storage_obj.id if storage_obj else None
        f.upload_status = "completed"
        f.change_type = session.change_type
        f.modified_time = session.file_mtime

    run.files_uploaded = (run.files_uploaded or 0) + 1
    run.bytes_uploaded = (run.bytes_uploaded or 0) + total_bytes

    event = RunEvent(
        run_id=run.id,
        event_type="UPLOAD_COMPLETED",
        message=f"File '{f.file_name}' upload completed via session {session_id}"
    )
    db.add(event)
    db.commit()
    db.refresh(f)

    return ApiResponse(success=True, data=_to_file_response(f), message="File upload session finalized successfully")


@router.get("/runs/{run_id}/state", response_model=ApiResponse[RunStateResponse])
def get_run_state(run_id: int, db: Session = Depends(get_db)):
    run = db.query(BackupRun).filter(BackupRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup run not found")
    return ApiResponse(
        success=True,
        data=RunStateResponse(
            run_id=run.id,
            state=run.state or "CREATED",
            status=run.status,
            lease_id=run.lease_id,
            lease_expires_at=run.lease_expires_at,
            interrupted_at=run.interrupted_at,
            resumed_at=run.resumed_at
        ),
        message="Run state retrieved"
    )


@router.post("/runs/{run_id}/state", response_model=ApiResponse[RunStateResponse])
def update_run_state(run_id: int, req: RunStateUpdateRequest, db: Session = Depends(get_db)):
    run = db.query(BackupRun).filter(BackupRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup run not found")

    new_state = req.state.upper()
    run.state = new_state
    if new_state in ("COMPLETED", "FAILED", "CANCELLED"):
        run.status = new_state.lower()
    elif new_state == "INTERRUPTED":
        run.interrupted_at = datetime.datetime.now(datetime.timezone.utc)
    elif new_state == "RESUMING":
        run.resumed_at = datetime.datetime.now(datetime.timezone.utc)

    event = RunEvent(
        run_id=run.id,
        event_type=f"STATE_{new_state}",
        message=req.message or f"Run transitioned to state {new_state}"
    )
    db.add(event)
    db.commit()
    db.refresh(run)

    return ApiResponse(
        success=True,
        data=RunStateResponse(
            run_id=run.id,
            state=run.state,
            status=run.status,
            lease_id=run.lease_id,
            lease_expires_at=run.lease_expires_at,
            interrupted_at=run.interrupted_at,
            resumed_at=run.resumed_at
        ),
        message=f"Run state updated to {new_state}"
    )


@router.post("/runs/{run_id}/checkpoint", response_model=ApiResponse[RunCheckpointResponse])
def record_run_checkpoint(run_id: int, req: RunCheckpointRequest, db: Session = Depends(get_db)):
    run = db.query(BackupRun).filter(BackupRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup run not found")

    cp = db.query(BackupCheckpoint).filter(BackupCheckpoint.run_id == run.id).first()
    now = datetime.datetime.now(datetime.timezone.utc)
    if not cp:
        cp = BackupCheckpoint(
            run_id=run.id,
            client_id=run.client_id,
            current_file=req.current_file,
            bytes_uploaded=req.bytes_uploaded,
            last_chunk_index=req.last_chunk_index,
            state=req.state,
            checkpoint_version=req.checkpoint_version
        )
        db.add(cp)
    else:
        cp.current_file = req.current_file
        cp.bytes_uploaded = req.bytes_uploaded
        cp.last_chunk_index = req.last_chunk_index
        cp.state = req.state
        cp.checkpoint_version = req.checkpoint_version
        cp.updated_at = now

    run.checkpoint_version = req.checkpoint_version
    run.state = req.state

    event = RunEvent(
        run_id=run.id,
        event_type="CHECKPOINT_WRITTEN",
        message=f"Checkpoint v{req.checkpoint_version} saved: {req.current_file} ({req.bytes_uploaded} bytes)"
    )
    db.add(event)
    db.commit()
    db.refresh(cp)

    return ApiResponse(
        success=True,
        data=RunCheckpointResponse(
            checkpoint_id=cp.id,
            run_id=cp.run_id,
            client_id=cp.client_id,
            state=cp.state,
            current_file=cp.current_file,
            bytes_uploaded=cp.bytes_uploaded,
            last_chunk_index=cp.last_chunk_index,
            checkpoint_version=cp.checkpoint_version,
            created_at=cp.created_at,
            updated_at=cp.updated_at
        ),
        message="Checkpoint recorded"
    )


@router.post("/runs/{run_id}/resume", response_model=ApiResponse[RunStateResponse])
def resume_backup_run(run_id: int, db: Session = Depends(get_db)):
    run = db.query(BackupRun).filter(BackupRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup run not found")
    if run.status in ("completed", "cancelled"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot resume run with status '{run.status}'")

    now = datetime.datetime.now(datetime.timezone.utc)
    run.state = "RESUMING"
    run.status = "running"
    run.resumed_at = now

    event = RunEvent(run_id=run.id, event_type="BACKUP_RESUMED", message="Run resumed")
    db.add(event)
    db.commit()
    db.refresh(run)

    return ApiResponse(
        success=True,
        data=RunStateResponse(
            run_id=run.id,
            state=run.state,
            status=run.status,
            lease_id=run.lease_id,
            lease_expires_at=run.lease_expires_at,
            interrupted_at=run.interrupted_at,
            resumed_at=run.resumed_at
        ),
        message="Run resumed"
    )


@router.post("/runs/{run_id}/interrupt", response_model=ApiResponse[RunStateResponse])
def interrupt_backup_run(run_id: int, db: Session = Depends(get_db)):
    run = db.query(BackupRun).filter(BackupRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup run not found")

    now = datetime.datetime.now(datetime.timezone.utc)
    run.state = "INTERRUPTED"
    run.interrupted_at = now

    event = RunEvent(run_id=run.id, event_type="BACKUP_INTERRUPTED", message="Run marked interrupted")
    db.add(event)
    db.commit()
    db.refresh(run)

    return ApiResponse(
        success=True,
        data=RunStateResponse(
            run_id=run.id,
            state=run.state,
            status=run.status,
            lease_id=run.lease_id,
            lease_expires_at=run.lease_expires_at,
            interrupted_at=run.interrupted_at,
            resumed_at=run.resumed_at
        ),
        message="Run marked interrupted"
    )


@router.post("/runs/{run_id}/cancel", response_model=ApiResponse[RunStateResponse])
def cancel_backup_run(run_id: int, db: Session = Depends(get_db)):
    run = db.query(BackupRun).filter(BackupRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup run not found")

    now = datetime.datetime.now(datetime.timezone.utc)
    run.state = "CANCELLED"
    run.status = "cancelled"
    run.completed_at = now
    if run.job:
        run.job.status = "cancelled"
        run.job.completed_at = now

    event = RunEvent(run_id=run.id, event_type="BACKUP_CANCELLED", message="Run cancelled by user/agent")
    db.add(event)
    db.commit()
    db.refresh(run)

    return ApiResponse(
        success=True,
        data=RunStateResponse(
            run_id=run.id,
            state=run.state,
            status=run.status,
            lease_id=run.lease_id,
            lease_expires_at=run.lease_expires_at,
            interrupted_at=run.interrupted_at,
            resumed_at=run.resumed_at
        ),
        message="Run cancelled"
    )


@router.post("/runs/{run_id}/lease/renew", response_model=ApiResponse[RunLeaseRenewResponse])
def renew_run_lease(run_id: int, req: RunLeaseRenewRequest, db: Session = Depends(get_db)):
    run = db.query(BackupRun).filter(BackupRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup run not found")
    if run.lease_id and run.lease_id != req.lease_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid lease ID")

    now = datetime.datetime.now(datetime.timezone.utc)
    new_expiry = now + datetime.timedelta(seconds=req.duration_seconds)
    run.lease_expires_at = new_expiry
    db.commit()

    return ApiResponse(
        success=True,
        data=RunLeaseRenewResponse(
            lease_id=run.lease_id or req.lease_id,
            lease_expires_at=new_expiry,
            is_valid=True
        ),
        message="Lease renewed successfully"
    )


@router.get("/runs/{run_id}/events", response_model=ApiResponse[List[RunEventResponse]])
def get_run_events(run_id: int, db: Session = Depends(get_db)):
    run = db.query(BackupRun).filter(BackupRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup run not found")

    events = db.query(RunEvent).filter(RunEvent.run_id == run_id).order_by(RunEvent.timestamp.asc()).all()
    results = [
        RunEventResponse(
            id=e.id,
            run_id=e.run_id,
            event_type=e.event_type,
            message=e.message,
            timestamp=e.timestamp,
            event_metadata=e.event_metadata
        )
        for e in events
    ]
    return ApiResponse(success=True, data=results, message=f"Retrieved {len(results)} events")
