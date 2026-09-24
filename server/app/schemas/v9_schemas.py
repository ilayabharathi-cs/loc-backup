"""Pydantic schemas for RetroVault V9 High Availability and Cluster APIs."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# --- Node Schemas ---
class ClusterNodeRegisterRequest(BaseModel):
    node_id: str
    hostname: str
    ip_address: str
    port: int = 8000
    roles: List[str] = Field(default_factory=lambda: ["CONTROL_PLANE", "WORKER"])
    capacity_weight: int = 1
    max_concurrent_jobs: int = 4
    metadata: Optional[Dict[str, Any]] = None


class ClusterNodeHeartbeatRequest(BaseModel):
    current_load: float = 0.0
    active_jobs_count: int = 0
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    disk_free_gb: Optional[float] = None


class ClusterNodeResponse(BaseModel):
    node_id: str
    hostname: str
    ip_address: str
    port: int
    roles: List[str]
    status: str
    current_load: float
    active_jobs_count: int
    max_concurrent_jobs: int
    last_heartbeat_at: Optional[str]
    registered_at: str
    is_draining: bool = False


# --- Leader Schemas ---
class LeaderStatusResponse(BaseModel):
    leader_node_id: Optional[str]
    is_active: bool
    lease_expires_at: Optional[str]
    last_leader: Optional[str] = None


class LeaderElectRequest(BaseModel):
    node_id: str
    ttl_seconds: Optional[int] = 15


class LeaderResignRequest(BaseModel):
    node_id: str


# --- Lock Schemas ---
class DistributedLockAcquireRequest(BaseModel):
    resource_key: str
    owner_node_id: str
    lock_type: str = "BACKUP_RUN"
    ttl_seconds: Optional[int] = 60


class DistributedLockReleaseRequest(BaseModel):
    resource_key: str
    lock_token: str


class DistributedLockResponse(BaseModel):
    acquired: bool
    token: Optional[str] = None
    resource_key: str
    expires_at: Optional[str] = None
    owner_node_id: Optional[str] = None


# --- Distributed Job Schemas ---
class DistributedJobCreateRequest(BaseModel):
    job_type: str  # BACKUP, RESTORE, REPLICATION, PRUNE, VERIFICATION
    priority: str = "NORMAL"  # CRITICAL, HIGH, NORMAL, LOW
    client_id: Optional[str] = None
    backup_job_id: Optional[int] = None
    repository_id: Optional[int] = None
    max_attempts: int = 3
    payload: Optional[Dict[str, Any]] = None


class DistributedJobClaimRequest(BaseModel):
    worker_node_id: str
    supported_job_types: Optional[List[str]] = None
    max_client_concurrency: int = 2
    max_repo_concurrency: int = 4


class DistributedJobHeartbeatRequest(BaseModel):
    progress_percent: Optional[float] = None
    status_message: Optional[str] = None


class DistributedJobCompleteRequest(BaseModel):
    status: str = "COMPLETED"  # COMPLETED, FAILED, CANCELLED
    error_message: Optional[str] = None
    result_metadata: Optional[Dict[str, Any]] = None


class DistributedJobResponse(BaseModel):
    id: int
    job_type: str
    priority: str
    priority_weight: int
    status: str
    client_id: Optional[str]
    backup_job_id: Optional[int]
    repository_id: Optional[int]
    owner_node_id: Optional[str]
    attempt_count: int
    max_attempts: int
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    error_message: Optional[str]
    payload: Optional[Dict[str, Any]]


# --- Cluster Topology & Diagnostics ---
class ClusterStatusResponse(BaseModel):
    cluster_status: str  # HEALTHY, DEGRADED, SPLIT_BRAIN_RISK
    total_nodes: int
    active_nodes: int
    leader: LeaderStatusResponse
    database: Dict[str, Any]
    backpressure: Dict[str, Any]
    categories: Dict[str, Any]
    active_locks_count: int
    queued_jobs_count: int
    running_jobs_count: int


# --- Bulk Fleet Schemas ---
class BulkTriggerRequest(BaseModel):
    client_ids: Optional[List[str]] = None
    job_type: str = "BACKUP"
    priority: str = "NORMAL"
    created_by: Optional[str] = "ADMIN"


class BulkOperationResponse(BaseModel):
    operation_id: str
    status: str
    target_count: int
    success_count: int
    failure_count: int
    job_ids: Optional[List[int]] = None
