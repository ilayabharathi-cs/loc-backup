"""Pydantic schemas for RetroVault V7 Enterprise Operations."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict
import datetime


# =============================================================================
# REPOSITORY SCHEMAS
# =============================================================================

class StorageRepositoryCreate(BaseModel):
    name: str
    repository_type: str = "LOCAL_FILESYSTEM"  # LOCAL_FILESYSTEM, REMOTE_FILESYSTEM, S3_COMPATIBLE
    path: str
    endpoint: Optional[str] = None
    root_path: Optional[str] = None
    total_bytes: int = 1024 * 1024 * 1024 * 500  # Default 500 GB
    status: str = "ONLINE"
    protection_mode: str = "NORMAL"  # NORMAL, PROTECTED, IMMUTABLE
    encryption_enabled: bool = False
    configuration: Optional[Dict[str, Any]] = None


class StorageRepositoryResponse(BaseModel):
    id: int
    name: str
    repository_type: str
    path: str
    endpoint: Optional[str] = None
    root_path: Optional[str] = None
    total_bytes: int
    used_bytes: int
    available_bytes: int
    capacity_bytes: int
    status: str
    protection_mode: str
    encryption_enabled: bool
    last_health_check: Optional[datetime.datetime] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class RepositoryHealthResponse(BaseModel):
    repository_id: int
    name: str
    type: str
    status: str
    protection_mode: str
    reachable: bool
    read_test: bool
    write_test: bool
    delete_test: bool
    latency_ms: float
    capacity_bytes: int
    used_bytes: int
    available_bytes: int
    free_percent: float
    object_count: int
    corrupted_object_count: int
    pending_gc_count: int
    pending_replication_jobs: int
    last_successful_backup: Optional[str] = None
    last_successful_replication: Optional[str] = None
    last_health_check: Optional[str] = None
    errors: List[str] = []


# =============================================================================
# REPLICATION SCHEMAS
# =============================================================================

class ReplicationJobCreate(BaseModel):
    source_repository_id: int
    destination_repository_id: int
    recovery_point_id: Optional[int] = None
    bandwidth_limit_mbps: Optional[float] = None
    execute_now: bool = True


class ReplicationItemResponse(BaseModel):
    id: int
    job_id: int
    storage_object_id: Optional[int]
    source_path: str
    destination_path: str
    stored_sha256: str
    content_sha256: str
    stored_size: int
    status: str
    retry_count: int
    error_message: Optional[str] = None
    transferred_at: Optional[datetime.datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ReplicationJobResponse(BaseModel):
    id: int
    job_id: str
    source_repository_id: int
    destination_repository_id: int
    recovery_point_id: Optional[int] = None
    status: str
    total_objects: int
    completed_objects: int
    failed_objects: int
    skipped_objects: int
    total_bytes: int
    transferred_bytes: int
    bandwidth_limit_mbps: Optional[float] = None
    progress_percent: float
    started_at: Optional[datetime.datetime] = None
    completed_at: Optional[datetime.datetime] = None
    error_message: Optional[str] = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class TopologyResponse(BaseModel):
    status: str
    is_compliant: bool
    total_repositories: int
    total_copies: int
    media_types: List[str]
    media_types_count: int
    has_offsite: bool
    offsite_repositories: List[str]
    primary_repositories: List[str]
    secondary_repositories: List[str]
    completed_replications: int
    missing_requirements: List[str]
    recommendation: str


# =============================================================================
# SECURITY & MFA SCHEMAS
# =============================================================================

class MfaSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str
    recovery_codes: List[str]


class MfaVerifyRequest(BaseModel):
    code: str


class AgentRotateRequest(BaseModel):
    reason: Optional[str] = "Routine credential rotation"


class AgentRotateResponse(BaseModel):
    client_id: str
    device_id: str
    new_token: str
    expires_at: Optional[str]
    message: str


# =============================================================================
# ALERT SCHEMAS
# =============================================================================

class AlertRuleCreate(BaseModel):
    name: str
    rule_type: str
    severity: str = "WARNING"
    threshold_value: Optional[str] = None
    is_enabled: bool = True
    description: Optional[str] = None


class AlertRuleResponse(BaseModel):
    id: int
    name: str
    rule_type: str
    severity: str
    threshold_value: Optional[str]
    is_enabled: bool
    description: Optional[str]
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class AlertResponse(BaseModel):
    id: int
    rule_id: Optional[int]
    alert_type: str
    severity: str
    title: str
    message: str
    status: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    acknowledged_by: Optional[str]
    acknowledged_at: Optional[datetime.datetime]
    resolved_at: Optional[datetime.datetime]
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# DR & HEALTH SCHEMAS
# =============================================================================

class DrTestRequest(BaseModel):
    recovery_point_id: Optional[int] = None


class DrTestResponse(BaseModel):
    test_id: str
    recovery_point_id: int
    result: str
    files_tested: int
    bytes_tested: int
    files_verified: int
    failures: int
    duration_seconds: float
    error_message: Optional[str]
    started_at: str
    completed_at: Optional[str]


# =============================================================================
# CENTRALIZED SETTINGS SCHEMAS
# =============================================================================

class SystemSettingUpdate(BaseModel):
    value: str
    description: Optional[str] = None


class SystemSettingResponse(BaseModel):
    id: int
    category: str
    key: str
    value: str
    description: Optional[str]
    updated_at: datetime.datetime
    updated_by: Optional[str]

    model_config = ConfigDict(from_attributes=True)
