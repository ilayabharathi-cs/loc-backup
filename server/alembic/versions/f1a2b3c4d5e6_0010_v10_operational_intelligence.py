"""0010_v10_operational_intelligence

Revision ID: f1a2b3c4d5e6
Revises: e1f2a3b4c5d6
Create Date: 2026-09-23 20:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "metric_samples",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("metric_name", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("labels_json", sa.Text(), nullable=True),
        sa.Column("granularity", sa.String(length=20), server_default="RAW", nullable=False),
        sa.Column("sample_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("min_value", sa.Float(), nullable=True),
        sa.Column("max_value", sa.Float(), nullable=True),
        sa.Column("sum_value", sa.Float(), nullable=True),
    )
    op.create_index("ix_metric_samples_name", "metric_samples", ["metric_name"])
    op.create_index("ix_metric_samples_timestamp", "metric_samples", ["timestamp"])
    op.create_index("ix_metric_samples_source", "metric_samples", ["source"])
    op.create_index("ix_metric_samples_granularity", "metric_samples", ["granularity"])

    op.create_table(
        "health_checks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("component", sa.String(length=80), nullable=False),
        sa.Column("check_type", sa.String(length=30), server_default="liveness", nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("latency_ms", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("last_success", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("details_json", sa.Text(), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_health_checks_component", "health_checks", ["component"])
    op.create_index("ix_health_checks_status", "health_checks", ["status"])
    op.create_index("ix_health_checks_checked_at", "health_checks", ["checked_at"])

    op.create_table(
        "operational_alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("alert_id", sa.String(length=100), unique=True, nullable=False),
        sa.Column("alert_type", sa.String(length=80), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="ACTIVE", nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("resource_id", sa.String(length=150), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("evidence_json", sa.Text(), nullable=True),
        sa.Column("threshold_value", sa.Float(), nullable=True),
        sa.Column("observed_value", sa.Float(), nullable=True),
        sa.Column("fingerprint", sa.String(length=120), nullable=False),
        sa.Column("occurrence_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by", sa.String(length=100), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(length=100), nullable=True),
        sa.Column("incident_id", sa.String(length=100), nullable=True),
    )
    op.create_index("ix_operational_alerts_alert_id", "operational_alerts", ["alert_id"])
    op.create_index("ix_operational_alerts_type", "operational_alerts", ["alert_type"])
    op.create_index("ix_operational_alerts_severity", "operational_alerts", ["severity"])
    op.create_index("ix_operational_alerts_status", "operational_alerts", ["status"])
    op.create_index("ix_operational_alerts_fingerprint", "operational_alerts", ["fingerprint"])

    op.create_table(
        "operational_incidents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("incident_id", sa.String(length=100), unique=True, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="DETECTED", nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("root_event", sa.String(length=255), nullable=False),
        sa.Column("relationship_type", sa.String(length=50), server_default="CAUSAL", nullable=False),
        sa.Column("affected_resources_json", sa.Text(), server_default="[]", nullable=False),
        sa.Column("child_alerts_json", sa.Text(), server_default="[]", nullable=False),
        sa.Column("timeline_json", sa.Text(), nullable=True),
        sa.Column("evidence_json", sa.Text(), nullable=True),
        sa.Column("mitigation_steps", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(length=100), nullable=True),
    )
    op.create_index("ix_operational_incidents_incident_id", "operational_incidents", ["incident_id"])
    op.create_index("ix_operational_incidents_status", "operational_incidents", ["status"])
    op.create_index("ix_operational_incidents_severity", "operational_incidents", ["severity"])

    op.create_table(
        "capacity_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("repository_id", sa.Integer(), sa.ForeignKey("storage_repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("logical_bytes", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("unique_content_bytes", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("compressed_bytes", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("physical_bytes", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("free_bytes", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("total_capacity_bytes", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("utilization_pct", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("dedup_ratio", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("compression_ratio", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("overall_efficiency", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("daily_growth_bytes", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("weekly_growth_bytes", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("monthly_growth_bytes", sa.BigInteger(), server_default="0", nullable=False),
    )
    op.create_index("ix_capacity_snapshots_repo", "capacity_snapshots", ["repository_id"])
    op.create_index("ix_capacity_snapshots_timestamp", "capacity_snapshots", ["timestamp"])

    op.create_table(
        "capacity_forecasts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("repository_id", sa.Integer(), sa.ForeignKey("storage_repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("method", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="PROJECTED", nullable=False),
        sa.Column("data_window_days", sa.Integer(), server_default="30", nullable=False),
        sa.Column("sample_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("daily_burn_rate_bytes", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("days_to_depletion", sa.Float(), nullable=True),
        sa.Column("estimated_depletion_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("forecast_7d_bytes", sa.BigInteger(), nullable=True),
        sa.Column("forecast_30d_bytes", sa.BigInteger(), nullable=True),
        sa.Column("forecast_90d_bytes", sa.BigInteger(), nullable=True),
        sa.Column("confidence_metric", sa.Float(), nullable=True),
        sa.Column("uncertainty_info_json", sa.Text(), nullable=True),
        sa.Column("is_projection", sa.Boolean(), server_default="1", nullable=False),
    )
    op.create_index("ix_capacity_forecasts_repo", "capacity_forecasts", ["repository_id"])
    op.create_index("ix_capacity_forecasts_generated_at", "capacity_forecasts", ["generated_at"])

    op.create_table(
        "compliance_evidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("evidence_id", sa.String(length=100), unique=True, nullable=False),
        sa.Column("domain", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("resource_type", sa.String(length=60), nullable=False),
        sa.Column("resource_id", sa.String(length=150), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence_summary", sa.Text(), nullable=False),
        sa.Column("evidence_payload_json", sa.Text(), nullable=True),
        sa.Column("verification_hash", sa.String(length=128), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_compliance_evidence_id", "compliance_evidence", ["evidence_id"])
    op.create_index("ix_compliance_evidence_domain", "compliance_evidence", ["domain"])
    op.create_index("ix_compliance_evidence_status", "compliance_evidence", ["status"])

    op.create_table(
        "compliance_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("report_id", sa.String(length=100), unique=True, nullable=False),
        sa.Column("report_type", sa.String(length=60), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scope", sa.String(length=100), server_default="GLOBAL", nullable=False),
        sa.Column("data_sources_json", sa.Text(), nullable=False),
        sa.Column("system_version", sa.String(length=30), server_default="10.0.0", nullable=False),
        sa.Column("evidence_summary_json", sa.Text(), nullable=False),
        sa.Column("exceptions_json", sa.Text(), nullable=True),
        sa.Column("unknowns_json", sa.Text(), nullable=True),
        sa.Column("generated_by", sa.String(length=100), server_default="SYSTEM", nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_compliance_reports_id", "compliance_reports", ["report_id"])
    op.create_index("ix_compliance_reports_type", "compliance_reports", ["report_type"])

    op.create_table(
        "report_executions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("execution_id", sa.String(length=100), unique=True, nullable=False),
        sa.Column("report_id", sa.String(length=100), nullable=False),
        sa.Column("format", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="COMPLETED", nullable=False),
        sa.Column("file_path", sa.String(length=255), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_report_executions_id", "report_executions", ["execution_id"])
    op.create_index("ix_report_executions_report_id", "report_executions", ["report_id"])


def downgrade() -> None:
    op.drop_table("report_executions")
    op.drop_table("compliance_reports")
    op.drop_table("compliance_evidence")
    op.drop_table("capacity_forecasts")
    op.drop_table("capacity_snapshots")
    op.drop_table("operational_incidents")
    op.drop_table("operational_alerts")
    op.drop_table("health_checks")
    op.drop_table("metric_samples")
