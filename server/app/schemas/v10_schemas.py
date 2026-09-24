"""Pydantic schemas for RetroVault V10 Operational Intelligence, Observability, Capacity & Compliance."""

from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field


# --- Metric Schemas ---
class MetricIngestRequest(BaseModel):
    metric_name: str
    value: float
    source: str = "custom"
    labels: Optional[Dict[str, Any]] = None
    granularity: str = "RAW"


class MetricBatchIngestRequest(BaseModel):
    samples: List[MetricIngestRequest]


class MetricSampleResponse(BaseModel):
    id: int
    metric_name: str
    value: float
    timestamp: Union[datetime, str]
    source: str
    labels: Optional[Dict[str, Any]] = None
    granularity: str


# --- Health Schemas ---
class ComponentHealthResponse(BaseModel):
    component: str
    status: str
    latency_ms: float
    last_success: Optional[Union[datetime, str]] = None
    last_failure: Optional[Union[datetime, str]] = None
    reason: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class SystemHealthResponse(BaseModel):
    overall_status: str
    overall_reason: str
    check_type: str
    evaluated_at: Union[datetime, str]
    components: Dict[str, ComponentHealthResponse]


# --- Alert Schemas ---
class AlertTriggerRequest(BaseModel):
    alert_type: str
    resource_id: str
    source: str
    title: str
    message: str
    severity: str = "WARNING"
    threshold_value: Optional[float] = None
    observed_value: Optional[float] = None
    evidence: Optional[Dict[str, Any]] = None


class AlertAcknowledgeRequest(BaseModel):
    acknowledged_by: Optional[str] = "admin"


class AlertResolveRequest(BaseModel):
    resolved_by: Optional[str] = "admin"


class AlertResponse(BaseModel):
    id: int
    alert_id: str
    alert_type: str
    severity: str
    status: str
    source: str
    resource_id: str
    title: str
    message: str
    occurrence_count: int
    first_seen_at: Union[datetime, str]
    last_seen_at: Union[datetime, str]
    incident_id: Optional[str] = None


# --- Incident Schemas ---
class IncidentCorrelateRequest(BaseModel):
    root_event: str
    title: str
    alert_ids: List[str]
    affected_resources: List[str]
    severity: str = "HIGH"
    relationship_type: str = "CAUSAL"
    evidence: Optional[Dict[str, Any]] = None


class IncidentUpdateRequest(BaseModel):
    status: str
    note: Optional[str] = None


class IncidentResponse(BaseModel):
    incident_id: str
    title: str
    status: str
    severity: str
    root_event: str
    relationship_type: str
    affected_resources: List[str]
    child_alerts: List[str]
    timeline: List[Dict[str, Any]]
    created_at: Union[datetime, str]
    updated_at: Union[datetime, str]
    resolved_at: Optional[Union[datetime, str]] = None


# --- Capacity Schemas ---
class CapacitySnapshotResponse(BaseModel):
    repository_id: int
    logical_bytes: int
    unique_content_bytes: int
    compressed_bytes: int
    physical_bytes: int
    free_bytes: int
    total_capacity_bytes: int
    utilization_pct: float
    dedup_ratio: float
    compression_ratio: float
    overall_efficiency: float
    timestamp: Union[datetime, str]


class CapacityForecastRequest(BaseModel):
    repository_id: int
    window_days: int = 30
    method: str = "linear_trend"


class CapacityForecastResponse(BaseModel):
    repository_id: int
    repository_name: Optional[str] = None
    status: str
    is_projection: bool = True
    method_used: str
    sample_count: int
    data_window_days: int
    current_used_bytes: Optional[int] = None
    total_capacity_bytes: Optional[int] = None
    free_bytes: Optional[int] = None
    daily_burn_rate_bytes: float = 0.0
    days_to_depletion: Optional[float] = None
    estimated_depletion_date: Optional[Union[datetime, str]] = None
    forecast_7d_bytes: Optional[int] = None
    forecast_30d_bytes: Optional[int] = None
    forecast_90d_bytes: Optional[int] = None
    confidence_r_squared: Optional[float] = None
    disclaimer: Optional[str] = None
    message: Optional[str] = None


# --- Compliance & Report Schemas ---
class ComplianceEvidenceResponse(BaseModel):
    evidence_id: str
    domain: str
    status: str
    resource_type: str
    resource_id: str
    period_start: Union[datetime, str]
    period_end: Union[datetime, str]
    evidence_summary: str
    verification_hash: str
    evaluated_at: Union[datetime, str]


class ReportGenerateRequest(BaseModel):
    report_type: str
    title: Optional[str] = None
    period_start: Optional[Union[datetime, str]] = None
    period_end: Optional[Union[datetime, str]] = None
    scope: str = "GLOBAL"


class ComplianceReportResponse(BaseModel):
    report_id: str
    report_type: str
    title: str
    period_start: Union[datetime, str]
    period_end: Union[datetime, str]
    scope: str
    system_version: str
    generated_by: str
    generated_at: Union[datetime, str]
    evidence_summary: Dict[str, Any]


class ReportExportRequest(BaseModel):
    format: str = "JSON"  # JSON, CSV, PDF


class ReportExecutionResponse(BaseModel):
    execution_id: str
    report_id: str
    format: str
    status: str
    file_path: Optional[str] = None
    file_size_bytes: int = 0
    checksum_sha256: Optional[str] = None
    created_at: Union[datetime, str]


# --- Recommendation Schemas ---
class RecommendationResponse(BaseModel):
    id: str
    severity: str
    affected_resource: str
    reason: str
    evidence: Dict[str, Any]
    recommended_action: str
    generated_at: Union[datetime, str]
    is_automated_execution_allowed: bool = False
