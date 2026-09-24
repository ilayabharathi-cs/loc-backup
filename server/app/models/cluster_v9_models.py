"""RetroVault V9 Cluster, High Availability, Distributed Queue & Fleet Models."""

import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import Integer, BigInteger, Float, String, Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class ClusterNode(Base):
    __tablename__ = "cluster_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    node_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    hostname: Mapped[str] = mapped_column(String(150), nullable=False)
    ip_address: Mapped[str] = mapped_column(String(60), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="CONTROL_PLANE", nullable=False)
    # Roles: CONTROL_PLANE, WORKER, SCHEDULER, REPOSITORY_WORKER
    status: Mapped[str] = mapped_column(String(30), default="STARTING", index=True, nullable=False)
    # Statuses: STARTING, HEALTHY, DEGRADED, DRAINING, MAINTENANCE, OFFLINE, UNKNOWN
    version: Mapped[str] = mapped_column(String(30), default="9.0.0", nullable=False)
    capabilities_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Capabilities: {"scheduler": true, "backup_worker": true, "restore_worker": true, "replication_worker": true, ...}
    last_heartbeat: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    draining_started_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    @property
    def port(self) -> int:
        return 8000

    @property
    def roles(self) -> list:
        return [self.role]

    @property
    def roles_json(self) -> str:
        import json
        return json.dumps([self.role])

    @property
    def current_load(self) -> float:
        return 0.0

    @property
    def active_jobs_count(self) -> int:
        return 0

    @property
    def max_concurrent_jobs(self) -> int:
        return 4

    @property
    def registered_at(self) -> datetime.datetime:
        return self.created_at

    @property
    def last_heartbeat_at(self) -> datetime.datetime:
        return self.last_heartbeat

    @property
    def is_draining(self) -> bool:
        return self.status == "DRAINING"


class ClusterLease(Base):
    __tablename__ = "cluster_leases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    lease_key: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    # e.g., "LEADER_ELECTION", "SCHEDULER_LEADER"
    owner_node_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    lease_token: Mapped[str] = mapped_column(String(100), nullable=False)
    lease_expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    acquired_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    renewed_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DistributedJob(Base):
    __tablename__ = "distributed_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    # Types: BACKUP, RESTORE, REPLICATION, INTEGRITY_SCAN, GC, RETENTION, DR_TEST, BULK_OPERATION
    priority: Mapped[str] = mapped_column(String(20), default="NORMAL", index=True, nullable=False)
    # Priorities: CRITICAL (1), HIGH (5), NORMAL (10), LOW (20)
    priority_weight: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="QUEUED", index=True, nullable=False)
    # Statuses: QUEUED, CLAIMED, RUNNING, PAUSED, RETRYING, COMPLETED, FAILED, CANCELLED, ORPHANED
    owner_node_id: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    client_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("clients.id", ondelete="SET NULL"), nullable=True, index=True)
    repository_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("storage_repositories.id", ondelete="SET NULL"), nullable=True, index=True)
    run_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("backup_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    available_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DistributedLock(Base):
    __tablename__ = "distributed_locks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    resource_key: Mapped[str] = mapped_column(String(200), unique=True, index=True, nullable=False)
    # e.g., "client:12:backup", "repo:3:gc", "repo:1:replication"
    lock_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # Types: BACKUP_RUN, RESTORE_RUN, REPLICATION_RUN, GC_RUN, RETENTION_RUN, INTEGRITY_SCAN, POLICY_APPLY, SECURITY_OPERATION
    owner_node_id: Mapped[str] = mapped_column(String(100), nullable=False)
    lock_token: Mapped[str] = mapped_column(String(100), nullable=False)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    acquired_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ClusterEvent(Base):
    __tablename__ = "cluster_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    event_type: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    # Types: NODE_JOINED, NODE_HEARTBEAT, NODE_LEFT, NODE_OFFLINE, NODE_DRAINING,
    #        LEADER_ELECTED, LEADER_CHANGED, LEADER_RESIGNED,
    #        JOB_QUEUED, JOB_CLAIMED, JOB_ORPHANED, JOB_REQUEUED, JOB_COMPLETED, JOB_FAILED,
    #        FAILOVER_STARTED, FAILOVER_COMPLETED, DATABASE_DEGRADED, WORKER_OFFLINE
    severity: Mapped[str] = mapped_column(String(20), default="INFO", index=True, nullable=False)
    # Severities: INFO, WARNING, ERROR, CRITICAL
    node_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    details_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class BulkOperation(Base):
    __tablename__ = "bulk_operations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    operation_id: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    operation_type: Mapped[str] = mapped_column(String(60), nullable=False)
    # Types: ASSIGN_POLICY, ASSIGN_GROUP, TRIGGER_BACKUP, REPOSITORY_MIGRATE, ASSIGN_SECURITY_PROFILE
    status: Mapped[str] = mapped_column(String(30), default="PENDING", index=True, nullable=False)
    # Statuses: PENDING, RUNNING, COMPLETED, FAILED, PARTIAL_FAILURE
    target_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    details_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
