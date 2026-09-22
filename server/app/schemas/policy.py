import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

class PolicyPathSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    path_type: str = "universal"  # universal, custom
    path_value: str
    is_excluded: bool = False

class PolicyBase(BaseModel):
    name: str
    description: Optional[str] = None
    backup_type: str = "incremental"  # full, incremental
    change_detection: str = "usn_journal"  # usn_journal, scheduled_scan
    rpo_target_seconds: int = Field(default=120, ge=30, le=86400)
    compression_enabled: bool = True
    encryption_enabled: bool = True
    cpu_limit_percent: int = Field(default=10, ge=1, le=100)
    network_limit_mbps: int = Field(default=100, ge=1, le=10000)
    retention_days: int = Field(default=7, ge=1, le=3650)
    is_active: bool = True

class PolicyCreate(PolicyBase):
    paths: List[PolicyPathSchema] = []

class PolicyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    backup_type: Optional[str] = None
    change_detection: Optional[str] = None
    rpo_target_seconds: Optional[int] = None
    compression_enabled: Optional[bool] = None
    encryption_enabled: Optional[bool] = None
    cpu_limit_percent: Optional[int] = None
    network_limit_mbps: Optional[int] = None
    retention_days: Optional[int] = None
    is_active: Optional[bool] = None
    paths: Optional[List[PolicyPathSchema]] = None

class PolicyResponse(PolicyBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime
    paths: List[PolicyPathSchema] = []
