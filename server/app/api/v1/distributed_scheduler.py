"""REST API endpoints for RetroVault V9 Distributed Scheduler and Job Queue."""

import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.v9_schemas import (
    DistributedJobCreateRequest,
    DistributedJobClaimRequest,
    DistributedJobHeartbeatRequest,
    DistributedJobCompleteRequest,
    DistributedJobResponse,
)
from app.models.cluster_v9_models import DistributedJob
from app.services.cluster.distributed_queue import DistributedJobQueue
from app.services.cluster.worker_pool import RepositoryWorkerPool

router = APIRouter(prefix="/scheduler", tags=["Distributed Scheduler"])


def _to_job_response(job: DistributedJob) -> DistributedJobResponse:
    return DistributedJobResponse(
        id=job.id,
        job_type=job.job_type,
        priority=job.priority,
        priority_weight=job.priority_weight,
        status=job.status,
        client_id=str(job.client_id) if job.client_id is not None else None,
        backup_job_id=getattr(job, "run_id", None),
        repository_id=job.repository_id,
        owner_node_id=job.owner_node_id,
        attempt_count=job.attempt_count,
        max_attempts=job.max_attempts,
        created_at=job.created_at.isoformat(),
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        error_message=job.error_message,
        payload=json.loads(job.payload_json) if job.payload_json else None,
    )


@router.post("/jobs", response_model=DistributedJobResponse)
def enqueue_job(payload: DistributedJobCreateRequest, db: Session = Depends(get_db)):
    queue = DistributedJobQueue(db)
    job = queue.enqueue_job(
        job_type=payload.job_type,
        priority=payload.priority,
        client_id=payload.client_id,
        backup_job_id=payload.backup_job_id,
        repository_id=payload.repository_id,
        payload=payload.payload,
        max_attempts=payload.max_attempts,
    )
    return _to_job_response(job)


@router.get("/jobs", response_model=List[DistributedJobResponse])
def list_jobs(
    status: Optional[str] = Query(None),
    job_type: Optional[str] = Query(None),
    limit: int = 50,
    db: Session = Depends(get_db)
):
    query = db.query(DistributedJob)
    if status:
        query = query.filter(DistributedJob.status == status.upper())
    if job_type:
        query = query.filter(DistributedJob.job_type == job_type.upper())
    jobs = query.order_by(DistributedJob.id.desc()).limit(limit).all()
    return [_to_job_response(j) for j in jobs]


@router.post("/jobs/claim", response_model=Optional[DistributedJobResponse])
def claim_job(payload: DistributedJobClaimRequest, db: Session = Depends(get_db)):
    queue = DistributedJobQueue(db)
    job = queue.claim_next_job(
        worker_node_id=payload.worker_node_id,
        supported_job_types=payload.supported_job_types,
        max_client_concurrency=payload.max_client_concurrency,
        max_repo_concurrency=payload.max_repo_concurrency,
    )
    if not job:
        return None
    return _to_job_response(job)


@router.post("/jobs/{job_id}/heartbeat")
def heartbeat_job(job_id: int, payload: DistributedJobHeartbeatRequest, db: Session = Depends(get_db)):
    queue = DistributedJobQueue(db)
    updated = queue.heartbeat_job(
        job_id=job_id,
        progress_percent=payload.progress_percent,
        status_message=payload.status_message,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Job not found or not in running state")
    return {"heartbeat_ack": True, "job_id": job_id}


@router.post("/jobs/{job_id}/complete")
def complete_job(job_id: int, payload: DistributedJobCompleteRequest, db: Session = Depends(get_db)):
    queue = DistributedJobQueue(db)
    completed = queue.complete_job(
        job_id=job_id,
        status=payload.status,
        error_message=payload.error_message,
        result_metadata=payload.result_metadata,
    )
    if not completed:
        raise HTTPException(status_code=404, detail="Job not found or already terminated")
    return {"completed": True, "job_id": job_id, "status": payload.status}


@router.get("/pools")
def get_worker_pools(db: Session = Depends(get_db)):
    pool = RepositoryWorkerPool(db)
    return {
        "categories": pool.get_category_utilization(),
        "backpressure": pool.evaluate_backpressure(),
    }
