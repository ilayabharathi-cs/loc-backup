"""RetroVault V11: Application-Aware Data Protection & Automated Recovery Models."""

import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import Integer, BigInteger, Float, String, Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class Workload(Base):
    """Discovered or configured application workload on a protected client."""
    __tablename__ = "workloads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    workload_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    client_id: Mapped[str] = mapped_column(String(100), ForeignKey("clients.id"), index=True, nullable=False)
    type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)  # WINDOWS_FILESYSTEM, MSSQL, POSTGRESQL, GENERIC_APP
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="DISCOVERED", index=True, nullable=False)  # DISCOVERED, PREPARING, QUIESCING, BACKING_UP, VERIFYING, COMPLETING, COMPLETED, FAILED, PARTIAL, CANCELLED
    health: Mapped[str] = mapped_column(String(50), default="HEALTHY", nullable=False)  # HEALTHY, WARNING, CRITICAL, UNKNOWN
    protection_state: Mapped[str] = mapped_column(String(50), default="UNPROTECTED", index=True, nullable=False)  # UNPROTECTED, PROTECTED, SUSPENDED, FAILED
    consistency_capability: Mapped[str] = mapped_column(String(50), default="UNKNOWN", nullable=False)  # APPLICATION_CONSISTENT, CRASH_CONSISTENT, FILE_SYSTEM_CONSISTENT, UNSUPPORTED
    last_protected_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_verified_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    config_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    protections: Mapped[List["WorkloadProtection"]] = relationship("WorkloadProtection", back_populates="workload", cascade="all, delete-orphan")
    artifacts: Mapped[List["WorkloadArtifact"]] = relationship("WorkloadArtifact", back_populates="workload", cascade="all, delete-orphan")
    backup_chains: Mapped[List["BackupChain"]] = relationship("BackupChain", back_populates="workload", cascade="all, delete-orphan")
    verifications: Mapped[List["RecoveryVerification"]] = relationship("RecoveryVerification", back_populates="workload", cascade="all, delete-orphan")


class WorkloadProviderConfig(Base):
    """Configuration and capabilities for a workload provider."""
    __tablename__ = "workload_providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    provider_type: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    capabilities_json: Mapped[str] = mapped_column(Text, nullable=False)
    settings_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class WorkloadProtection(Base):
    """Association linking a workload to a protection policy and schedule."""
    __tablename__ = "workload_protections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    workload_id: Mapped[str] = mapped_column(String(100), ForeignKey("workloads.workload_id"), index=True, nullable=False)
    policy_id: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    backup_mode: Mapped[str] = mapped_column(String(30), default="FULL", nullable=False)  # FULL, LOG, INCREMENTAL
    schedule_cron: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)
    settings_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    workload: Mapped["Workload"] = relationship("Workload", back_populates="protections")


class WorkloadArtifact(Base):
    """An artifact generated during application-aware backup stored in CAS."""
    __tablename__ = "workload_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    artifact_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    workload_id: Mapped[str] = mapped_column(String(100), ForeignKey("workloads.workload_id"), index=True, nullable=False)
    recovery_point_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    artifact_name: Mapped[str] = mapped_column(String(255), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(50), nullable=False)  # DATA, LOG, WAL_LOG, METADATA, DUMP
    storage_object_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True, nullable=False)

    workload: Mapped["Workload"] = relationship("Workload", back_populates="artifacts")


class ApplicationConsistencyRecord(Base):
    """Factual, evidence-based consistency record for a Recovery Point."""
    __tablename__ = "application_consistency_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    record_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    recovery_point_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    workload_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    consistency_state: Mapped[str] = mapped_column(String(50), index=True, nullable=False)  # FILE_SYSTEM_CONSISTENT, APPLICATION_CONSISTENT, CRASH_CONSISTENT, PARTIAL, UNKNOWN, FAILED
    verification_method: Mapped[str] = mapped_column(String(80), nullable=False)
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False)
    verified_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True, nullable=False)
    verified_by: Mapped[str] = mapped_column(String(100), default="SYSTEM", nullable=False)


class BackupChain(Base):
    """Metadata tracking relationship, continuity and validity of backup sets."""
    __tablename__ = "backup_chains"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    chain_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    workload_id: Mapped[str] = mapped_column(String(100), ForeignKey("workloads.workload_id"), index=True, nullable=False)
    base_recovery_point_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    latest_recovery_point_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    chain_length: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="VALID", index=True, nullable=False)  # VALID, DEGRADED, BROKEN, UNKNOWN
    broken_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_validated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    workload: Mapped["Workload"] = relationship("Workload", back_populates="backup_chains")


class RecoveryVerification(Base):
    """Automated restore verification execution in an isolated sandbox."""
    __tablename__ = "recovery_verifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    verification_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    recovery_point_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    workload_id: Mapped[str] = mapped_column(String(100), ForeignKey("workloads.workload_id"), index=True, nullable=False)
    verification_type: Mapped[str] = mapped_column(String(50), nullable=False)  # MANIFEST, CHECKSUM, FULL_RESTORE, APPLICATION_ARTIFACT, DATABASE_VALIDATION, RECONSTRUCTION
    sandbox_path: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="PENDING", index=True, nullable=False)  # PENDING, RUNNING, VERIFIED, FAILED, CANCELLED
    started_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True, nullable=False)

    workload: Mapped["Workload"] = relationship("Workload", back_populates="verifications")
    steps: Mapped[List["RecoveryVerificationStep"]] = relationship("RecoveryVerificationStep", back_populates="verification", cascade="all, delete-orphan")


class RecoveryVerificationStep(Base):
    """Individual step executed during automated recovery verification."""
    __tablename__ = "recovery_verification_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    verification_id: Mapped[str] = mapped_column(String(100), ForeignKey("recovery_verifications.verification_id"), index=True, nullable=False)
    step_name: Mapped[str] = mapped_column(String(100), nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="PENDING", index=True, nullable=False)  # PENDING, RUNNING, PASSED, FAILED
    details_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    verification: Mapped["RecoveryVerification"] = relationship("RecoveryVerification", back_populates="steps")


class RecoveryReadiness(Base):
    """Factual, objective recovery readiness calculation based on measurable signals."""
    __tablename__ = "recovery_readiness_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    workload_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    client_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    readiness_state: Mapped[str] = mapped_column(String(30), index=True, nullable=False)  # READY, DEGRADED, NOT_READY, UNKNOWN
    contributing_signals_json: Mapped[str] = mapped_column(Text, nullable=False)
    latest_backup_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    latest_verified_rp_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    rpo_compliance_percent: Mapped[float] = mapped_column(Float, default=100.0, nullable=False)
    rto_estimate_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    evaluated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True, nullable=False)


class PolicyLifecycle(Base):
    """Audited lifecycle management and versioning for backup policies."""
    __tablename__ = "policy_lifecycles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    policy_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    lifecycle_state: Mapped[str] = mapped_column(String(30), default="DRAFT", index=True, nullable=False)  # DRAFT, VALIDATING, APPROVED, ACTIVE, SUSPENDED, RETIRED
    definition_json: Mapped[str] = mapped_column(Text, nullable=False)
    effective_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(100), default="SYSTEM", nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    approvals: Mapped[List["PolicyApproval"]] = relationship("PolicyApproval", back_populates="lifecycle", cascade="all, delete-orphan")


class PolicyApproval(Base):
    """Explicit sign-off and approval record for a policy lifecycle version."""
    __tablename__ = "policy_approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    policy_lifecycle_id: Mapped[int] = mapped_column(Integer, ForeignKey("policy_lifecycles.id"), index=True, nullable=False)
    requested_by: Mapped[str] = mapped_column(String(100), nullable=False)
    approved_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="PENDING", index=True, nullable=False)  # PENDING, APPROVED, REJECTED
    approval_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    approved_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    lifecycle: Mapped["PolicyLifecycle"] = relationship("PolicyLifecycle", back_populates="approvals")


class RemediationAction(Base):
    """Safe, auditable remediation workflows with approval gates."""
    __tablename__ = "remediation_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    remediation_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    action_type: Mapped[str] = mapped_column(String(60), index=True, nullable=False)  # RETRY_BACKUP, RERUN_VERIFICATION, REENABLE_PROTECTION, MOVE_REPOSITORY, TRIGGER_REPLICATION, ROTATE_CREDENTIALS, START_RECOVERY_VERIFICATION
    target_resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_resource_id: Mapped[str] = mapped_column(String(150), index=True, nullable=False)
    requires_dual_approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    first_approver: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    second_approver: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="PENDING_APPROVAL", index=True, nullable=False)  # PENDING_APPROVAL, APPROVED, EXECUTING, COMPLETED, FAILED, REJECTED
    execution_result_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    audit_event_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True, nullable=False)
    executed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class DependencyRelation(Base):
    """Logical dependency graph preventing unsafe cleanup or orphan deletions."""
    __tablename__ = "dependency_relations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    parent_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)  # CLIENT, POLICY, WORKLOAD, BACKUP_JOB, RUN, RECOVERY_POINT, MANIFEST, CAS_OBJECT, REPLICATION, VERIFICATION
    parent_id: Mapped[str] = mapped_column(String(150), index=True, nullable=False)
    child_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    child_id: Mapped[str] = mapped_column(String(150), index=True, nullable=False)
    relation_type: Mapped[str] = mapped_column(String(50), default="REQUIRES", nullable=False)  # REQUIRES, CONTAINS, DERIVED_FROM, REPLICATED_TO
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True, nullable=False)
