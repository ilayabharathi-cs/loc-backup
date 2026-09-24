"""0007_v7_enterprise_operations

Revision ID: c1d2e3f4a5b6
Revises: b1c2d3e4f5a6
Create Date: 2026-09-23 16:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update storage_repositories
    with op.batch_alter_table("storage_repositories") as batch_op:
        batch_op.add_column(sa.Column("endpoint", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("root_path", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("protection_mode", sa.String(length=20), server_default="NORMAL", nullable=False))
        batch_op.add_column(sa.Column("encryption_enabled", sa.Boolean(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("last_health_check", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("configuration", sa.Text(), nullable=True))

    # 2. replication_jobs
    op.create_table(
        "replication_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.String(length=50), nullable=False, unique=True),
        sa.Column("source_repository_id", sa.Integer(), sa.ForeignKey("storage_repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("destination_repository_id", sa.Integer(), sa.ForeignKey("storage_repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recovery_point_id", sa.Integer(), sa.ForeignKey("recovery_points.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(length=30), server_default="CREATED", nullable=False),
        sa.Column("total_objects", sa.Integer(), server_default="0", nullable=False),
        sa.Column("completed_objects", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed_objects", sa.Integer(), server_default="0", nullable=False),
        sa.Column("skipped_objects", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_bytes", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("transferred_bytes", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("bandwidth_limit_mbps", sa.Float(), nullable=True),
        sa.Column("progress_percent", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_replication_jobs_job_id", "replication_jobs", ["job_id"])
    op.create_index("ix_replication_jobs_status", "replication_jobs", ["status"])

    # 3. replication_items
    op.create_table(
        "replication_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("replication_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("storage_object_id", sa.Integer(), sa.ForeignKey("storage_objects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_path", sa.String(length=1000), nullable=False),
        sa.Column("destination_path", sa.String(length=1000), nullable=False),
        sa.Column("stored_sha256", sa.String(length=64), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("stored_size", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="PENDING", nullable=False),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("transferred_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_replication_items_job_id", "replication_items", ["job_id"])
    op.create_index("ix_replication_items_status", "replication_items", ["status"])
    op.create_index("ix_replication_items_content_sha", "replication_items", ["content_sha256"])

    # 4. replication_checkpoints
    op.create_table(
        "replication_checkpoints",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("replication_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("last_completed_item_id", sa.Integer(), nullable=True),
        sa.Column("completed_objects", sa.Integer(), server_default="0", nullable=False),
        sa.Column("transferred_bytes", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("checkpoint_state", sa.String(length=50), server_default="ACTIVE", nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_replication_checkpoints_job_id", "replication_checkpoints", ["job_id"])

    # 5. alert_rules
    op.create_table(
        "alert_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), unique=True, nullable=False),
        sa.Column("rule_type", sa.String(length=50), nullable=False),
        sa.Column("severity", sa.String(length=20), server_default="WARNING", nullable=False),
        sa.Column("threshold_value", sa.String(length=100), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_alert_rules_rule_type", "alert_rules", ["rule_type"])

    # 6. alerts
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rule_id", sa.Integer(), sa.ForeignKey("alert_rules.id", ondelete="SET NULL"), nullable=True),
        sa.Column("alert_type", sa.String(length=50), nullable=False),
        sa.Column("severity", sa.String(length=20), server_default="WARNING", nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="ACTIVE", nullable=False),
        sa.Column("resource_type", sa.String(length=50), nullable=True),
        sa.Column("resource_id", sa.String(length=100), nullable=True),
        sa.Column("acknowledged_by", sa.String(length=100), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_alerts_status", "alerts", ["status"])
    op.create_index("ix_alerts_severity", "alerts", ["severity"])

    # 7. notification_channels
    op.create_table(
        "notification_channels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), unique=True, nullable=False),
        sa.Column("channel_type", sa.String(length=30), nullable=False),
        sa.Column("target", sa.String(length=500), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("configuration", sa.Text(), nullable=True),
        sa.Column("cooldown_seconds", sa.Integer(), server_default="300", nullable=False),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 8. notification_deliveries
    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("channel_id", sa.Integer(), sa.ForeignKey("notification_channels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alert_id", sa.Integer(), sa.ForeignKey("alerts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="SENT", nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 9. agent_credentials
    op.create_table(
        "agent_credentials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="ACTIVE", nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rotation_reason", sa.String(length=255), nullable=True),
    )
    op.create_index("ix_agent_credentials_client_id", "agent_credentials", ["client_id"])
    op.create_index("ix_agent_credentials_token_hash", "agent_credentials", ["token_hash"])

    # 10. mfa_settings
    op.create_table(
        "mfa_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("secret_encrypted", sa.String(length=500), nullable=False),
        sa.Column("recovery_codes_hash", sa.Text(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 11. system_settings
    op.create_table(
        "system_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("key", sa.String(length=100), unique=True, nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_by", sa.String(length=100), nullable=True),
    )
    op.create_index("ix_system_settings_category", "system_settings", ["category"])
    op.create_index("ix_system_settings_key", "system_settings", ["key"])

    # 12. dr_tests
    op.create_table(
        "dr_tests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("test_id", sa.String(length=50), unique=True, nullable=False),
        sa.Column("recovery_point_id", sa.Integer(), sa.ForeignKey("recovery_points.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_path", sa.String(length=1000), nullable=False),
        sa.Column("files_tested", sa.Integer(), server_default="0", nullable=False),
        sa.Column("bytes_tested", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("files_verified", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failures", sa.Integer(), server_default="0", nullable=False),
        sa.Column("duration_seconds", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("result", sa.String(length=30), server_default="PASSED", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_dr_tests_test_id", "dr_tests", ["test_id"])
    op.create_index("ix_dr_tests_result", "dr_tests", ["result"])


def downgrade() -> None:
    op.drop_table("dr_tests")
    op.drop_table("system_settings")
    op.drop_table("mfa_settings")
    op.drop_table("agent_credentials")
    op.drop_table("notification_deliveries")
    op.drop_table("notification_channels")
    op.drop_table("alerts")
    op.drop_table("alert_rules")
    op.drop_table("replication_checkpoints")
    op.drop_table("replication_items")
    op.drop_table("replication_jobs")
    with op.batch_alter_table("storage_repositories") as batch_op:
        batch_op.drop_column("configuration")
        batch_op.drop_column("last_health_check")
        batch_op.drop_column("encryption_enabled")
        batch_op.drop_column("protection_mode")
        batch_op.drop_column("root_path")
        batch_op.drop_column("endpoint")
