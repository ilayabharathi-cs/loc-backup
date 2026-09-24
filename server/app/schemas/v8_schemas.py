"""Pydantic schemas for RetroVault V8 Enterprise Security, Ransomware Resilience & Fleet."""

import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# Security Profile Schemas
class SecurityProfileBase(BaseModel):
    name: str
    description: Optional[str] = None
    anomaly_threshold: int = Field(default=60, ge=1, le=100)
    max_deletion_count: int = Field(default=5, ge=1)
    max_deletion_pct: float = Field(default=10.0, ge=0.1, le=100.0)
    require_mfa_for_deletion: bool = True
    entropy_threshold: float = Field(default=7.2, ge=0.0, le=8.0)
    is_default: bool = False


class SecurityProfileCreate(SecurityProfileBase):
    pass


class SecurityProfileResponse(SecurityProfileBase):
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True


# Client Group Schemas
class ClientGroupBase(BaseModel):
    name: str
    description: Optional[str] = None
    policy_id: Optional[int] = None
    security_profile_id: Optional[int] = None
    repository_id: Optional[int] = None


class ClientGroupCreate(ClientGroupBase):
    pass


class ClientGroupResponse(ClientGroupBase):
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True


# Security Event Schemas
class SecurityEventResponse(BaseModel):
    id: int
    event_type: str
    severity: str
    client_id: Optional[int] = None
    repository_id: Optional[int] = None
    run_id: Optional[int] = None
    recovery_point_id: Optional[int] = None
    score: int
    description: str
    evidence_json: Optional[str] = None
    status: str
    created_at: datetime.datetime
    acknowledged_at: Optional[datetime.datetime] = None
    resolved_at: Optional[datetime.datetime] = None
    resolved_by: Optional[str] = None

    class Config:
        from_attributes = True


# Security Incident Schemas
class SecurityIncidentCreate(BaseModel):
    title: str
    severity: str = "HIGH"
    client_id: Optional[int] = None
    candidate_recovery_point_id: Optional[int] = None
    containment_notes: Optional[str] = None


class SecurityIncidentTransition(BaseModel):
    status: str
    notes: Optional[str] = None
    candidate_rp_id: Optional[int] = None


class SecurityIncidentResponse(BaseModel):
    id: int
    incident_number: str
    title: str
    severity: str
    status: str
    client_id: Optional[int] = None
    candidate_recovery_point_id: Optional[int] = None
    restore_test_id: Optional[str] = None
    containment_notes: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    closed_at: Optional[datetime.datetime] = None
    closed_by: Optional[str] = None

    class Config:
        from_attributes = True


# Integrity Scan Schemas
class IntegrityScanTrigger(BaseModel):
    repository_id: int
    scan_type: str = "FULL"  # FULL, SAMPLE
    sample_limit: Optional[int] = None


class IntegrityScanResponse(BaseModel):
    id: int
    scan_id: str
    repository_id: int
    scan_type: str
    total_objects: int
    valid_objects: int
    corrupted_objects: int
    missing_objects: int
    duration_seconds: float
    status: str
    details_json: Optional[str] = None
    created_at: datetime.datetime

    class Config:
        from_attributes = True


# Deletion Guard Schemas
class DeletionGuardRequest(BaseModel):
    request_type: str
    target_resource_type: str
    target_resource_id: str
    payload: Dict[str, Any]


class DeletionGuardApproval(BaseModel):
    mfa_code: Optional[str] = None


class DeletionGuardResponse(BaseModel):
    id: int
    request_type: str
    requester_username: str
    target_resource_type: str
    target_resource_id: str
    payload_json: str
    status: str
    risk_score: int
    approved_by: Optional[str] = None
    approved_at: Optional[datetime.datetime] = None
    expires_at: datetime.datetime
    created_at: datetime.datetime

    class Config:
        from_attributes = True


# Simulation Schemas
class SimulationTrigger(BaseModel):
    scenario_type: str = "RANSOMWARE_ENCRYPTION_BURST"
    file_count: int = 20
    encryption_ratio: float = 0.8


class SimulationResponse(BaseModel):
    id: int
    simulation_id: str
    scenario_type: str
    status: str
    sandbox_path: str
    parameters_json: Optional[str] = None
    results_json: Optional[str] = None
    started_at: datetime.datetime
    completed_at: Optional[datetime.datetime] = None

    class Config:
        from_attributes = True


# Recovery Point Protection Schemas
class RecoveryPointProtectionUpdate(BaseModel):
    protection_state: str  # NORMAL, PROTECTED, RETENTION_LOCKED, SECURITY_HOLD, QUARANTINED
    hold_days: Optional[int] = 30
    reason: Optional[str] = "Manual protection update"
