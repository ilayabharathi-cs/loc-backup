import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class RetentionPolicyCreate(BaseModel):
    name: str
    policy_id: Optional[int] = None
    keep_last: int = 10
    daily: int = 7
    weekly: int = 4
    monthly: int = 12
    yearly: int = 7
    timezone: str = "UTC"
    is_active: bool = True


class RetentionPolicyUpdate(BaseModel):
    name: Optional[str] = None
    policy_id: Optional[int] = None
    keep_last: Optional[int] = None
    daily: Optional[int] = None
    weekly: Optional[int] = None
    monthly: Optional[int] = None
    yearly: Optional[int] = None
    timezone: Optional[str] = None
    is_active: Optional[bool] = None


class RetentionPolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    policy_id: Optional[int] = None
    keep_last: int
    daily: int
    weekly: int
    monthly: int
    yearly: int
    timezone: str
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime


class RetentionEvaluationTrigger(BaseModel):
    retention_policy_id: Optional[int] = None
    client_id: Optional[int] = None


class RetentionEvaluationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    retention_policy_id: Optional[int] = None
    evaluated_at: datetime.datetime
    total_recovery_points: int
    protected_count: int
    expired_count: int
    reclaimed_bytes: int
    details: Optional[str] = None


class ManualProtectionRequest(BaseModel):
    protect: bool = True
