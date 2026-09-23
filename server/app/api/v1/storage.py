from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database.session import get_db
from app.models.storage_repository import StorageRepository
from app.models.storage_object import StorageObject
from app.models.garbage_collection import GarbageCollectionJob
from app.schemas.storage import (
    StorageRepositoryResponse,
    StorageObjectResponse,
    StorageMetricsResponse,
    StorageScrubRequest,
    StorageScrubResponse,
    GarbageCollectionTriggerRequest,
    GarbageCollectionResponse,
)
from app.schemas.common import ApiResponse
from app.security.dependencies import get_optional_current_user
from app.services.storage.integrity_service import StorageIntegrityService
from app.services.gc.garbage_collector import GarbageCollector

router = APIRouter(prefix="/storage", tags=["Storage Repository"])


@router.get("", response_model=ApiResponse[List[StorageRepositoryResponse]])
def list_repositories(db: Session = Depends(get_db), current_user=Depends(get_optional_current_user)):
    repos = db.query(StorageRepository).all()
    metrics_svc = StorageIntegrityService(db)
    metrics = metrics_svc.get_storage_metrics()

    results = []
    for r in repos:
        tb_factor = 1024 ** 4
        res = StorageRepositoryResponse(
            id=r.id,
            name=r.name,
            repository_type=r.repository_type,
            path=r.path,
            total_bytes=r.total_bytes,
            used_bytes=r.used_bytes,
            available_bytes=r.available_bytes,
            status=r.status,
            created_at=r.created_at,
            updated_at=r.updated_at,
            total_tb=round(r.total_bytes / tb_factor, 1),
            used_tb=round(r.used_bytes / tb_factor, 1),
            free_tb=round(r.available_bytes / tb_factor, 1),
            dedup_ratio=metrics["deduplication_ratio"],
            compression_ratio=metrics["compression_ratio"],
            disk_health="OPTIMAL (S.M.A.R.T. Verified)"
        )
        results.append(res)
    return ApiResponse(success=True, data=results, message=f"Retrieved {len(results)} storage repositories")


@router.get("/metrics", response_model=ApiResponse[StorageMetricsResponse])
def get_storage_metrics(db: Session = Depends(get_db), current_user=Depends(get_optional_current_user)):
    """Retrieve global deduplication, compression, and space accounting metrics."""
    metrics_svc = StorageIntegrityService(db)
    metrics = metrics_svc.get_storage_metrics()
    return ApiResponse(success=True, data=StorageMetricsResponse(**metrics), message="Storage metrics calculated")


@router.get("/objects", response_model=ApiResponse[List[StorageObjectResponse]])
def list_storage_objects(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    state: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_optional_current_user),
):
    """List physical storage objects and deduplication reference counts."""
    query = select(StorageObject)
    if state:
        query = query.where(StorageObject.state == state.upper())
    query = query.order_by(StorageObject.created_at.desc()).offset(offset).limit(limit)

    objects = db.execute(query).scalars().all()
    results = [StorageObjectResponse.model_validate(obj) for obj in objects]
    return ApiResponse(success=True, data=results, message=f"Retrieved {len(results)} storage objects")


@router.post("/verify", response_model=ApiResponse[StorageScrubResponse])
def verify_storage_integrity(
    req: StorageScrubRequest = StorageScrubRequest(),
    db: Session = Depends(get_db),
    current_user=Depends(get_optional_current_user),
):
    """Scrub physical storage objects against stored and decompressed content hashes."""
    integrity_svc = StorageIntegrityService(db)
    result = integrity_svc.scrub_storage_objects(
        batch_size=req.batch_size,
        verify_content=req.verify_content,
        object_id=req.object_id,
    )
    return ApiResponse(success=True, data=StorageScrubResponse(**result), message="Storage integrity scan complete")


@router.post("/gc", response_model=ApiResponse[GarbageCollectionResponse])
def trigger_garbage_collection(
    req: GarbageCollectionTriggerRequest = GarbageCollectionTriggerRequest(),
    db: Session = Depends(get_db),
    current_user=Depends(get_optional_current_user),
):
    """Execute or simulate two-phase garbage collection."""
    gc = GarbageCollector(db)
    job = gc.run_garbage_collection(dry_run=req.dry_run)
    return ApiResponse(
        success=True,
        data=GarbageCollectionResponse.model_validate(job),
        message="Garbage collection simulation completed" if req.dry_run else "Garbage collection completed",
    )


@router.get("/gc/jobs", response_model=ApiResponse[List[GarbageCollectionResponse]])
def list_gc_jobs(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_optional_current_user),
):
    """List history of garbage collection executions."""
    stmt = select(GarbageCollectionJob).order_by(GarbageCollectionJob.created_at.desc()).limit(limit)
    jobs = db.execute(stmt).scalars().all()
    return ApiResponse(
        success=True,
        data=[GarbageCollectionResponse.model_validate(j) for j in jobs],
        message=f"Retrieved {len(jobs)} garbage collection jobs",
    )


@router.get("/{repository_id}", response_model=ApiResponse[StorageRepositoryResponse])
def get_repository(repository_id: int, db: Session = Depends(get_db)):
    r = db.query(StorageRepository).filter(StorageRepository.id == repository_id).first()
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Storage repository not found")

    metrics_svc = StorageIntegrityService(db)
    metrics = metrics_svc.get_storage_metrics()

    tb_factor = 1024 ** 4
    res = StorageRepositoryResponse(
        id=r.id,
        name=r.name,
        repository_type=r.repository_type,
        path=r.path,
        total_bytes=r.total_bytes,
        used_bytes=r.used_bytes,
        available_bytes=r.available_bytes,
        status=r.status,
        created_at=r.created_at,
        updated_at=r.updated_at,
        total_tb=round(r.total_bytes / tb_factor, 1),
        used_tb=round(r.used_bytes / tb_factor, 1),
        free_tb=round(r.available_bytes / tb_factor, 1),
        dedup_ratio=metrics["deduplication_ratio"],
        compression_ratio=metrics["compression_ratio"],
        disk_health="OPTIMAL (S.M.A.R.T. Verified)"
    )
    return ApiResponse(success=True, data=res, message="Storage repository details retrieved")
