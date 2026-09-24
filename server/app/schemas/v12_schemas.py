"""Pydantic schemas for RetroVault V12 Cloud & Hybrid Storage Tiering."""

import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


# ------------------------------------------------------------------------------
# Cloud Credentials Schemas
# ------------------------------------------------------------------------------

class CloudCredentialCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150, description="Unique human-readable identifier")
    provider: str = Field(default="s3", description="Provider type (s3, minio, wasabi, mock)")
    access_key: str = Field(..., min_length=1, description="Access Key ID / Username")
    secret_key: str = Field(..., min_length=1, description="Secret Access Key / Password")
    endpoint: Optional[str] = Field(default=None, description="Custom endpoint for MinIO/Wasabi/self-hosted")
    region: Optional[str] = Field(default="us-east-1", description="Provider region")
    prefix: Optional[str] = Field(default=None, description="Optional root prefix")
    use_tls: bool = Field(default=True, description="Enforce HTTPS transport")
    verify_ssl: bool = Field(default=True, description="Verify TLS certificate validity")


class CloudCredentialResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    credential_id: str
    name: str
    provider: str
    endpoint: Optional[str] = None
    region: Optional[str] = None
    prefix: Optional[str] = None
    use_tls: bool
    verify_ssl: bool
    access_key_masked: str
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ------------------------------------------------------------------------------
# Storage Tier Schemas
# ------------------------------------------------------------------------------

class StorageTierCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150, description="Storage tier name")
    tier_type: str = Field(default="CLOUD_S3", description="Tier classification (HOT, WARM, COLD, ARCHIVE, CLOUD_S3)")
    provider: str = Field(default="s3", description="Provider backend (s3, minio, wasabi, mock)")
    credential_id: Optional[str] = Field(default=None, description="Reference to CloudCredential id or credential_id")
    bucket: str = Field(..., min_length=1, max_length=255, description="Target bucket name")
    prefix: Optional[str] = Field(default="", description="Base object prefix in bucket")
    object_lock_enabled: bool = Field(default=False, description="Enable WORM Object Lock")
    retention_period_days: int = Field(default=0, ge=0, description="WORM retention period in days")
    immutability_mode: str = Field(default="NONE", description="WORM mode: NONE, GOVERNANCE, COMPLIANCE")
    is_default: bool = Field(default=False, description="Set as default cloud offload tier")


class StorageTierUpdate(BaseModel):
    name: Optional[str] = None
    bucket: Optional[str] = None
    prefix: Optional[str] = None
    object_lock_enabled: Optional[bool] = None
    retention_period_days: Optional[int] = None
    immutability_mode: Optional[str] = None
    is_enabled: Optional[bool] = None


class StorageTierResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tier_id: str
    name: str
    tier_type: str
    provider: str
    credential_id: Optional[int] = None
    bucket: str
    prefix: Optional[str] = None
    state: str
    object_lock_enabled: bool
    retention_period_days: int
    immutability_mode: str
    is_default: bool
    is_enabled: bool
    last_validated_at: Optional[datetime.datetime] = None
    error_message: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class StorageTierValidateResponse(BaseModel):
    tier_id: str
    state: str
    valid: bool
    latency_ms: Optional[float] = None
    details: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ------------------------------------------------------------------------------
# Object Offload Schemas
# ------------------------------------------------------------------------------

class OffloadRequest(BaseModel):
    storage_object_ids: List[str] = Field(..., min_length=1, description="List of CAS StorageObject IDs to offload")


class OffloadItemResponse(BaseModel):
    object_id: str
    offload_id: Optional[str] = None
    size: Optional[int] = None
    status: str
    error: Optional[str] = None


class OffloadResponse(BaseModel):
    total: int
    offloaded_count: int
    failed_count: int
    items: List[OffloadItemResponse]


class RemoteVerificationResponse(BaseModel):
    object_id: str
    tier_id: str
    remote_key: str
    exists: bool
    remote_size: Optional[int] = None
    expected_size: Optional[int] = None
    checksum_verified: Optional[bool] = None
    verification_status: str
    error: Optional[str] = None
