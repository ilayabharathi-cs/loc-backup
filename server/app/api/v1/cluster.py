"""REST API endpoints for RetroVault V9 Cluster Management, Leader Election, and Locks."""

import json
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.v9_schemas import (
    ClusterNodeRegisterRequest,
    ClusterNodeHeartbeatRequest,
    ClusterNodeResponse,
    LeaderStatusResponse,
    LeaderElectRequest,
    LeaderResignRequest,
    DistributedLockAcquireRequest,
    DistributedLockReleaseRequest,
    DistributedLockResponse,
    ClusterStatusResponse,
)
from app.models.cluster_v9_models import ClusterEvent, DistributedLock, DistributedJob
from app.services.cluster.node_service import NodeHeartbeatService
from app.services.cluster.leader_election import LeaderElectionService
from app.services.cluster.lock_service import DistributedLockService
from app.services.cluster.cluster_reconciliation import ClusterReconciliationService
from app.services.cluster.worker_pool import RepositoryWorkerPool
from app.services.cluster.database_health import DatabaseHealthProvider

router = APIRouter(prefix="/cluster", tags=["Cluster Management"])


# --- Node Management ---
@router.post("/nodes/register", response_model=ClusterNodeResponse)
def register_node(payload: ClusterNodeRegisterRequest, db: Session = Depends(get_db)):
    service = NodeHeartbeatService(db)
    node = service.register_node(
        node_id=payload.node_id,
        hostname=payload.hostname,
        ip_address=payload.ip_address,
        port=payload.port,
        roles=payload.roles,
        capacity_weight=payload.capacity_weight,
        max_concurrent_jobs=payload.max_concurrent_jobs,
        metadata=payload.metadata,
    )
    return ClusterNodeResponse(
        node_id=node.node_id,
        hostname=node.hostname,
        ip_address=node.ip_address,
        port=node.port,
        roles=json.loads(node.roles_json) if node.roles_json else [],
        status=node.status,
        current_load=node.current_load,
        active_jobs_count=node.active_jobs_count,
        max_concurrent_jobs=node.max_concurrent_jobs,
        last_heartbeat_at=node.last_heartbeat_at.isoformat() if node.last_heartbeat_at else None,
        registered_at=node.registered_at.isoformat(),
        is_draining=node.is_draining,
    )


@router.post("/nodes/{node_id}/heartbeat")
def heartbeat_node(node_id: str, payload: ClusterNodeHeartbeatRequest, db: Session = Depends(get_db)):
    service = NodeHeartbeatService(db)
    success = service.heartbeat_node(
        node_id=node_id,
        current_load=payload.current_load,
        active_jobs_count=payload.active_jobs_count,
        metrics={
            "cpu_percent": payload.cpu_percent,
            "memory_percent": payload.memory_percent,
            "disk_free_gb": payload.disk_free_gb,
        }
    )
    if not success:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not registered")
    return {"status": "HEARTBEAT_ACK", "node_id": node_id}


@router.get("/nodes", response_model=List[ClusterNodeResponse])
def list_nodes(active_only: bool = False, db: Session = Depends(get_db)):
    service = NodeHeartbeatService(db)
    nodes = service.list_nodes(active_only=active_only)
    return [
        ClusterNodeResponse(
            node_id=n.node_id,
            hostname=n.hostname,
            ip_address=n.ip_address,
            port=n.port,
            roles=json.loads(n.roles_json) if n.roles_json else [],
            status=n.status,
            current_load=n.current_load,
            active_jobs_count=n.active_jobs_count,
            max_concurrent_jobs=n.max_concurrent_jobs,
            last_heartbeat_at=n.last_heartbeat_at.isoformat() if n.last_heartbeat_at else None,
            registered_at=n.registered_at.isoformat(),
            is_draining=n.is_draining,
        )
        for n in nodes
    ]


@router.post("/nodes/{node_id}/drain")
def drain_node(node_id: str, db: Session = Depends(get_db)):
    service = NodeHeartbeatService(db)
    res = service.set_node_draining(node_id=node_id, draining=True)
    if not res.get("updated"):
        raise HTTPException(status_code=404, detail=res.get("error", "Node not found"))
    return res


@router.post("/nodes/{node_id}/resume")
def resume_node(node_id: str, db: Session = Depends(get_db)):
    service = NodeHeartbeatService(db)
    res = service.set_node_draining(node_id=node_id, draining=False)
    if not res.get("updated"):
        raise HTTPException(status_code=404, detail=res.get("error", "Node not found"))
    return res


@router.post("/nodes/{node_id}/deregister")
def deregister_node(node_id: str, db: Session = Depends(get_db)):
    service = NodeHeartbeatService(db)
    res = service.deregister_node(node_id)
    return res


# --- Leader Election ---
@router.get("/leader", response_model=LeaderStatusResponse)
def get_leader(db: Session = Depends(get_db)):
    service = LeaderElectionService(db)
    return service.get_current_leader()


@router.post("/leader/elect")
def elect_leader(payload: LeaderElectRequest, db: Session = Depends(get_db)):
    service = LeaderElectionService(db)
    res = service.try_acquire_or_renew_leadership(node_id=payload.node_id, ttl_seconds=payload.ttl_seconds)
    return res


@router.post("/leader/resign")
def resign_leader(payload: LeaderResignRequest, db: Session = Depends(get_db)):
    service = LeaderElectionService(db)
    res = service.resign_leadership(node_id=payload.node_id)
    return res


# --- Distributed Locks ---
@router.post("/locks/acquire", response_model=DistributedLockResponse)
def acquire_lock(payload: DistributedLockAcquireRequest, db: Session = Depends(get_db)):
    service = DistributedLockService(db)
    res = service.acquire_lock(
        resource_key=payload.resource_key,
        owner_node_id=payload.owner_node_id,
        lock_type=payload.lock_type,
        ttl_seconds=payload.ttl_seconds
    )
    return DistributedLockResponse(
        acquired=res["acquired"],
        token=res.get("token"),
        resource_key=res["resource_key"],
        expires_at=res.get("expires_at"),
        owner_node_id=res.get("owner_node_id")
    )


@router.post("/locks/release")
def release_lock(payload: DistributedLockReleaseRequest, db: Session = Depends(get_db)):
    service = DistributedLockService(db)
    released = service.release_lock(resource_key=payload.resource_key, lock_token=payload.lock_token)
    return {"released": released, "resource_key": payload.resource_key}


# --- Cluster Diagnostics & Health ---
@router.get("/status", response_model=ClusterStatusResponse)
def get_cluster_status(db: Session = Depends(get_db)):
    node_service = NodeHeartbeatService(db)
    leader_service = LeaderElectionService(db)
    worker_pool = RepositoryWorkerPool(db)
    db_health = DatabaseHealthProvider(db)

    nodes = node_service.list_nodes(active_only=False)
    active_nodes = [n for n in nodes if n.status in ["ACTIVE", "HEALTHY", "READY"]]
    leader = leader_service.get_current_leader()

    active_locks = db.query(DistributedLock).count()
    queued_jobs = db.query(DistributedJob).filter(DistributedJob.status == "QUEUED").count()
    running_jobs = db.query(DistributedJob).filter(DistributedJob.status.in_(["CLAIMED", "RUNNING"])).count()

    bp = worker_pool.evaluate_backpressure()
    categories = worker_pool.get_category_utilization()
    db_stat = db_health.check_health()

    cluster_status = "HEALTHY"
    if not leader["is_active"] or len(active_nodes) == 0:
        cluster_status = "DEGRADED"
    if bp["backpressure_level"] in ["HIGH", "CRITICAL"]:
        cluster_status = "DEGRADED"

    return ClusterStatusResponse(
        cluster_status=cluster_status,
        total_nodes=len(nodes),
        active_nodes=len(active_nodes),
        leader=LeaderStatusResponse(**leader),
        database=db_stat,
        backpressure=bp,
        categories=categories,
        active_locks_count=active_locks,
        queued_jobs_count=queued_jobs,
        running_jobs_count=running_jobs,
    )


@router.post("/reconcile")
def reconcile_cluster(leader_node_id: str, force: bool = False, db: Session = Depends(get_db)):
    service = ClusterReconciliationService(db, leader_node_id=leader_node_id)
    res = service.reconcile_cluster(force=force)
    return res


@router.get("/events")
def list_cluster_events(limit: int = 50, db: Session = Depends(get_db)):
    events = db.query(ClusterEvent).order_by(ClusterEvent.id.desc()).limit(limit).all()
    return [
        {
            "id": e.id,
            "event_type": e.event_type,
            "severity": e.severity,
            "node_id": e.node_id,
            "details": json.loads(e.details_json) if e.details_json else {},
            "created_at": e.created_at.isoformat()
        }
        for e in events
    ]
