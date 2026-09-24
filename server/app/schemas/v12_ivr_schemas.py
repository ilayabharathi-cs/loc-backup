"""Pydantic schemas for RetroVault V12 Instant Virtual Recovery."""

import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class VirtualRecoverySessionCreate(BaseModel):
    recovery_point_id: int = Field(..., description="Target Recovery Point ID to virtually mount")
    target_path: str = Field(..., min_length=1, max_length=1000, description="Filesystem directory where virtual mount will be exposed")
    client_id: Optional[int] = Field(default=None, description="Client authorization ID")
    workload_id: Optional[str] = Field(default=None, description="Optional workload application ID")
    cloud_tier_id: Optional[int] = Field(default=None, description="Optional Cloud Storage Tier ID for fallback fetching")
    provider_type: str = Field(default="LOCAL_VIRTUAL", description="Provider type (LOCAL_VIRTUAL, MOCK)")


class VirtualRecoverySessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: str
    recovery_point_id: int
    client_id: int
    workload_id: Optional[str] = None
    target_path: str
    mount_point: Optional[str] = None
    provider_type: str
    cloud_tier_id: Optional[int] = None
    state: str
    hydration_status: str
    total_files: int
    total_bytes: int
    hydrated_files: int
    hydrated_bytes: int
    hydration_speed_bps: float
    hydration_eta_seconds: Optional[float] = None
    read_requests_count: int
    bytes_read: int
    cache_hits: int
    cache_misses: int
    cache_bytes: int
    time_to_first_access_ms: Optional[float] = None
    time_to_app_ready_ms: Optional[float] = None
    time_to_full_hydration_ms: Optional[float] = None
    error_message: Optional[str] = None
    created_at: datetime.datetime
    mounted_at: Optional[datetime.datetime] = None
    completed_at: Optional[datetime.datetime] = None


class PrefetchRequest(BaseModel):
    paths: List[str] = Field(..., min_length=1, description="List of relative file paths to prefetch into cache")


class HydrationRequest(BaseModel):
    max_files: Optional[int] = Field(default=None, ge=1, description="Max files to hydrate in this batch")


class VirtualRecoveryMetricsResponse(BaseModel):
    session_id: str
    state: str
    hydration_status: str
    total_files: int
    total_bytes: int
    hydrated_files: int
    hydrated_bytes: int
    hydration_speed_bps: float
    hydration_eta_seconds: Optional[float] = None
    read_requests_count: int
    bytes_read: int
    cache_hits: int
    cache_misses: int
    cache_hit_ratio: float
    cache_bytes: int
    time_to_first_access_ms: Optional[float] = None
    time_to_app_ready_ms: Optional[float] = None
    time_to_full_hydration_ms: Optional[float] = None
