"""0009_v9_high_availability

Revision ID: e1f2a3b4c5d6
Revises: d1e2f3a4b5c6
Create Date: 2026-09-23 17:35:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cluster_nodes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("node_id", sa.String(length=100), unique=True, nullable=False),
        sa.Column("hostname", sa.String(length=150), nullable=False),
        sa.Column("ip_address", sa.String(length=60), nullable=False),
        sa.Column("role", sa.String(length=50), server_default="CONTROL_PLANE", nullable=False),
        sa.Column("status", sa.String(length=30), server_default="STARTING", nullable=False),
        sa.Column("version", sa.String(length=30), server_default="9.0.0", nullable=False),
        sa.Column("capabilities_json", sa.Text(), nullable=True),
        sa.Column("last_heartbeat", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("draining_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    )

    op.create_table(
        "cluster_leases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lease_key", sa.String(length=100), unique=True, nullable=False),
        sa.Column("owner_node_id", sa.String(length=100), nullable=False),
        sa.Column("lease_token", sa.String(length=100), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("renewed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    )

    op.create_table(
        "distributed_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_type", sa.String(length=50), nullable=False),
        sa.Column("priority", sa.String(length=20), server_default="NORMAL", nullable=False),
        sa.Column("priority_weight", sa.Integer(), server_default="10", nullable=False),
        sa.Column("status", sa.String(length=30), server_default="QUEUED", nullable=False),
        sa.Column("owner_node_id", sa.String(length=100), nullable=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id", ondelete="SET NULL"), nullable=True),
        sa.Column("repository_id", sa.Integer(), sa.ForeignKey("storage_repositories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("backup_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    )

    op.create_table(
        "distributed_locks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("resource_key", sa.String(length=200), unique=True, nullable=False),
        sa.Column("lock_type", sa.String(length=50), nullable=False),
        sa.Column("owner_node_id", sa.String(length=100), nullable=False),
        sa.Column("lock_token", sa.String(length=100), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    )

    op.create_table(
        "cluster_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("severity", sa.String(length=20), server_default="INFO", nullable=False),
        sa.Column("node_id", sa.String(length=100), nullable=True),
        sa.Column("details_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    )

    op.create_table(
        "bulk_operations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("operation_id", sa.String(length=50), unique=True, nullable=False),
        sa.Column("operation_type", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="PENDING", nullable=False),
        sa.Column("target_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("success_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failure_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("skipped_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("details_json", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    )


def downgrade() -> None:
    op.drop_table("bulk_operations")
    op.drop_table("cluster_events")
    op.drop_table("distributed_locks")
    op.drop_table("distributed_jobs")
    op.drop_table("cluster_leases")
    op.drop_table("cluster_nodes")
