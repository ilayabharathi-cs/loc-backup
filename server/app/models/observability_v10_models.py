"""RetroVault V10 Operational Intelligence, Observability, Capacity & Compliance Models."""

import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import Integer, BigInteger, Float, String, Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class MetricSample(Base):
    """Time-series metric sample with low-cardinality labels and downsampling support."""
    __tablename__ = "metric_samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    metric_name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    labels_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    granularity: Mapped[str] = mapped_column(String(20), default="RAW", index=True, nullable=False)  # RAW, HOURLY, DAILY, MONTHLY
    sample_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    min_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sum_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class HealthCheck(Base):
    """Component-level health check execution recording factual status and latency."""
    __tablename__ = "health_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    component: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    check_type: Mapped[str] = mapped_column(String(30), default="liveness", nullable=False)  # liveness, readiness, deep_health
    status: Mapped[str] = mapped_column(String(30), index=True, nullable=False)  # HEALTHY, DEGRADED, WARNING, CRITICAL, UNKNOWN
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    last_success: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True, nullable=False)


class OperationalAlert(Base):
    """Operational alert with deduplication, cooldown, threshold, and correlation tracking."""
    __tablename__ = "operational_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    alert_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    alert_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), index=True, nullable=False)  # INFO, WARNING, ERROR, CRITICAL
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", index=True, nullable=False)  # ACTIVE, ACKNOWLEDGED, RESOLVED, SUPPRESSED
    source: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    resource_id: Mapped[str] = mapped_column(String(150), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    threshold_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    observed_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fingerprint: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    first_seen_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    acknowledged_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    resolved_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    incident_id: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)


class OperationalIncident(Base):
    """Correlated operational incident grouping multiple alerts and root-cause evidence."""
    __tablename__ = "operational_incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    incident_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="DETECTED", index=True, nullable=False)  # DETECTED, ACKNOWLEDGED, INVESTIGATING, MITIGATING, MONITORING, RESOLVED, CLOSED
    severity: Mapped[str] = mapped_column(String(20), index=True, nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    root_event: Mapped[str] = mapped_column(String(255), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(50), default="CAUSAL", nullable=False)  # CAUSAL, RELATED_EVENT
    affected_resources_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    child_alerts_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    timeline_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mitigation_steps: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resolved_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)


class CapacitySnapshot(Base):
    """Point-in-time storage and repository utilization snapshot for trend analysis."""
    __tablename__ = "capacity_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    repository_id: Mapped[int] = mapped_column(Integer, ForeignKey("storage_repositories.id", ondelete="CASCADE"), index=True, nullable=False)
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True, nullable=False)
    logical_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    unique_content_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    compressed_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    physical_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    free_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total_capacity_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    utilization_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    dedup_ratio: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    compression_ratio: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    overall_efficiency: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    daily_growth_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    weekly_growth_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    monthly_growth_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)


class CapacityForecast(Base):
    """Mathematical projection of repository capacity exhaustion with confidence bounds."""
    __tablename__ = "capacity_forecasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    repository_id: Mapped[int] = mapped_column(Integer, ForeignKey("storage_repositories.id", ondelete="CASCADE"), index=True, nullable=False)
    generated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True, nullable=False)
    method: Mapped[str] = mapped_column(String(50), nullable=False)  # linear_trend, rolling_average, growth_rate
    status: Mapped[str] = mapped_column(String(30), default="PROJECTED", nullable=False)  # PROJECTED, INSUFFICIENT_DATA
    data_window_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    daily_burn_rate_bytes: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    days_to_depletion: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    estimated_depletion_date: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    forecast_7d_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    forecast_30d_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    forecast_90d_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    confidence_metric: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    uncertainty_info_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_projection: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ComplianceEvidence(Base):
    """Factual immutable evidence item across 13 compliance and regulatory domains."""
    __tablename__ = "compliance_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    evidence_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    domain: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    # domains: backup_execution, backup_success, retention, immutability, restore_tests,
    # replication, integrity_scans, access_control, mfa, audit_events, policy_changes,
    # deletion_approvals, security_incidents
    status: Mapped[str] = mapped_column(String(40), index=True, nullable=False)  # EVIDENCE_AVAILABLE, EVIDENCE_MISSING, NOT_APPLICABLE, UNKNOWN
    resource_type: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    resource_id: Mapped[str] = mapped_column(String(150), index=True, nullable=False)
    period_start: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    period_end: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    evidence_summary: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    verification_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    evaluated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True, nullable=False)


class ComplianceReport(Base):
    """Auditable enterprise report record with factual source bindings."""
    __tablename__ = "compliance_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    report_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    report_type: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    # report_types: backup_operations, recovery_readiness, security_controls, access_control,
    # retention, immutability, replication, audit_activity, fleet_health, capacity_forecast,
    # comprehensive_compliance
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    period_start: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scope: Mapped[str] = mapped_column(String(100), default="GLOBAL", nullable=False)
    data_sources_json: Mapped[str] = mapped_column(Text, nullable=False)
    system_version: Mapped[str] = mapped_column(String(30), default="10.0.0", nullable=False)
    evidence_summary_json: Mapped[str] = mapped_column(Text, nullable=False)
    exceptions_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    unknowns_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    generated_by: Mapped[str] = mapped_column(String(100), default="SYSTEM", nullable=False)
    generated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True, nullable=False)


class ReportExecution(Base):
    """Physical artifact generation execution record for CSV, JSON, or PDF exports."""
    __tablename__ = "report_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    execution_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    report_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    format: Mapped[str] = mapped_column(String(20), index=True, nullable=False)  # JSON, CSV, PDF
    status: Mapped[str] = mapped_column(String(30), default="COMPLETED", nullable=False)  # PENDING, RUNNING, COMPLETED, FAILED
    file_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    checksum_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
