"""Pydantic schemas for RetroVault V11 Application-Aware Data Protection & Automated Recovery."""

from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field


# --- Workload Schemas ---
class WorkloadBase(BaseModel):
    client_id: str
    type: str  # WINDOWS_FILESYSTEM, MSSQL, POSTGRESQL, GENERIC_APP
    name: str
    version: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class WorkloadCreate(WorkloadBase):
    workload_id: Optional[str] = None


class WorkloadResponse(BaseModel):
    id: int
    workload_id: str
    client_id: str
    type: str
    name: str
    version: Optional[str] = None
    status: str
    health: str
    protection_state: str
    consistency_capability: str
    last_protected_at: Optional[Union[datetime, str]] = None
    last_verified_at: Optional[Union[datetime, str]] = None
    config: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: Union[datetime, str]
    updated_at: Union[datetime, str]


class WorkloadDiscoverRequest(BaseModel):
    provider_type: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class WorkloadProtectRequest(BaseModel):
    backup_type: str = "FULL"  # FULL, LOG, INCREMENTAL
    context_override: Optional[Dict[str, Any]] = None


class WorkloadRestorePreviewRequest(BaseModel):
    recovery_point_id: str
    target_destination: str
    recovery_mode: str = "APPLICATION_RESTORE"
    target_client_id: Optional[str] = None


class WorkloadRestoreRequest(BaseModel):
    recovery_point_id: str
    target_destination: str
    recovery_mode: str = "APPLICATION_RESTORE"
    target_client_id: Optional[str] = None


# --- Verification Schemas ---
class RecoveryVerificationCreate(BaseModel):
    recovery_point_id: str
    workload_id: str
    verification_type: str = "CHECKSUM"  # MANIFEST, CHECKSUM, FULL_RESTORE, APPLICATION_ARTIFACT, DATABASE_VALIDATION, RECONSTRUCTION


class RecoveryVerificationStepResponse(BaseModel):
    step_name: str
    step_order: int
    status: str
    details: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class RecoveryVerificationResponse(BaseModel):
    id: int
    verification_id: str
    recovery_point_id: str
    workload_id: str
    verification_type: str
    sandbox_path: str
    status: str
    duration_ms: float
    error_message: Optional[str] = None
    evidence: Optional[Dict[str, Any]] = None
    created_at: Union[datetime, str]
    started_at: Optional[Union[datetime, str]] = None
    completed_at: Optional[Union[datetime, str]] = None
    steps: Optional[List[RecoveryVerificationStepResponse]] = None


# --- Readiness Schemas ---
class RecoveryReadinessResponse(BaseModel):
    workload_id: str
    readiness_state: str  # READY, DEGRADED, NOT_READY, UNKNOWN
    rpo_compliance_percent: float
    rto_estimate_seconds: Optional[float] = None
    contributing_signals: Dict[str, Any]
    blocking_factors: List[str] = []
    degrading_factors: List[str] = []
    evaluated_at: Union[datetime, str]


# --- Backup Chain Schemas ---
class BackupChainResponse(BaseModel):
    id: int
    chain_id: str
    workload_id: str
    base_recovery_point_id: str
    latest_recovery_point_id: str
    chain_length: int
    status: str
    broken_reason: Optional[str] = None
    last_validated_at: Union[datetime, str]


# --- Policy Orchestration Schemas ---
class PolicyVersionCreate(BaseModel):
    policy_id: str
    definition: Dict[str, Any]


class PolicyApprovalRequest(BaseModel):
    notes: Optional[str] = None


class PolicyRollbackRequest(BaseModel):
    target_version: int


class PolicyLifecycleResponse(BaseModel):
    id: int
    policy_id: str
    version: int
    lifecycle_state: str
    definition: Dict[str, Any]
    effective_at: Optional[Union[datetime, str]] = None
    created_by: str
    created_at: Union[datetime, str]
    updated_at: Union[datetime, str]


# --- Remediation Schemas ---
class RemediationProposeRequest(BaseModel):
    action_type: str
    target_resource_type: str
    target_resource_id: str
    requires_dual_approval: bool = False


class RemediationApproveRequest(BaseModel):
    pass


class RemediationActionResponse(BaseModel):
    id: int
    remediation_id: str
    action_type: str
    target_resource_type: str
    target_resource_id: str
    requires_dual_approval: bool
    first_approver: Optional[str] = None
    second_approver: Optional[str] = None
    status: str
    execution_result: Optional[Dict[str, Any]] = None
    created_at: Union[datetime, str]
    executed_at: Optional[Union[datetime, str]] = None


# --- Dependency Schemas ---
class DependencyCheckRequest(BaseModel):
    resource_type: str
    resource_id: str


class DependencyCheckResponse(BaseModel):
    resource_type: str
    resource_id: str
    is_safe_to_delete: bool
    blockers: List[str]
