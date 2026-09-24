"""0008_v8_security_resilience

Revision ID: d1e2f3a4b5c6
Revises: c1d2e3f4a5b6
Create Date: 2026-09-23 16:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update clients table
    with op.batch_alter_table("clients") as batch_op:
        batch_op.add_column(sa.Column("group_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("policy_override_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("effective_policy_version", sa.Integer(), nullable=True))

    # 2. Update recovery_points table
    with op.batch_alter_table("recovery_points") as batch_op:
        batch_op.add_column(sa.Column("protection_state", sa.String(length=30), server_default="NORMAL", nullable=False))
        batch_op.add_column(sa.Column("security_hold_until", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("protected_reason", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("protected_by", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("protection_created_at", sa.DateTime(timezone=True), nullable=True))

    # 3. Update storage_repositories table
    with op.batch_alter_table("storage_repositories") as batch_op:
        batch_op.add_column(sa.Column("immutability_state", sa.String(length=30), server_default="DISABLED", nullable=False))
        batch_op.add_column(sa.Column("capabilities_json", sa.Text(), nullable=True))

    # 4. Update storage_objects table
    with op.batch_alter_table("storage_objects") as batch_op:
        batch_op.add_column(sa.Column("quarantined_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("quarantine_reason", sa.String(length=255), nullable=True))

    # 5. Create security_profiles table
    op.create_table(
        "security_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), unique=True, nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("anomaly_threshold", sa.Integer(), server_default="60", nullable=False),
        sa.Column("max_deletion_count", sa.Integer(), server_default="5", nullable=False),
        sa.Column("max_deletion_pct", sa.Float(), server_default="10.0", nullable=False),
        sa.Column("require_mfa_for_deletion", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("entropy_threshold", sa.Float(), server_default="7.2", nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    )

    # 6. Create client_groups table
    op.create_table(
        "client_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), unique=True, nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("policy_id", sa.Integer(), sa.ForeignKey("backup_policies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("security_profile_id", sa.Integer(), sa.ForeignKey("security_profiles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("repository_id", sa.Integer(), sa.ForeignKey("storage_repositories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    )

    # 7. Create policy_versions table
    op.create_table(
        "policy_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("policy_id", sa.Integer(), sa.ForeignKey("backup_policies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("definition_json", sa.Text(), nullable=False),
        sa.Column("change_summary", sa.String(length=255), nullable=True),
        sa.Column("created_by", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    )

    # 8. Create security_events table
    op.create_table(
        "security_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("severity", sa.String(length=20), server_default="MEDIUM", nullable=False),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id", ondelete="SET NULL"), nullable=True),
        sa.Column("repository_id", sa.Integer(), sa.ForeignKey("storage_repositories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("backup_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("recovery_point_id", sa.Integer(), sa.ForeignKey("recovery_points.id", ondelete="SET NULL"), nullable=True),
        sa.Column("score", sa.Integer(), server_default="0", nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("evidence_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), server_default="OPEN", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(length=100), nullable=True)
    )

    # 9. Create security_incidents table
    op.create_table(
        "security_incidents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("incident_number", sa.String(length=50), unique=True, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("severity", sa.String(length=20), server_default="HIGH", nullable=False),
        sa.Column("status", sa.String(length=40), server_default="DETECTED", nullable=False),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id", ondelete="SET NULL"), nullable=True),
        sa.Column("candidate_recovery_point_id", sa.Integer(), sa.ForeignKey("recovery_points.id", ondelete="SET NULL"), nullable=True),
        sa.Column("restore_test_id", sa.String(length=50), nullable=True),
        sa.Column("containment_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by", sa.String(length=100), nullable=True)
    )

    # 10. Create configuration_drifts table
    op.create_table(
        "configuration_drifts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("drift_type", sa.String(length=50), nullable=False),
        sa.Column("expected_value", sa.String(length=255), nullable=False),
        sa.Column("actual_value", sa.String(length=255), nullable=False),
        sa.Column("severity", sa.String(length=20), server_default="WARNING", nullable=False),
        sa.Column("status", sa.String(length=30), server_default="DETECTED", nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True)
    )

    # 11. Create integrity_scans table
    op.create_table(
        "integrity_scans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scan_id", sa.String(length=50), unique=True, nullable=False),
        sa.Column("repository_id", sa.Integer(), sa.ForeignKey("storage_repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scan_type", sa.String(length=30), server_default="FULL", nullable=False),
        sa.Column("total_objects", sa.Integer(), server_default="0", nullable=False),
        sa.Column("valid_objects", sa.Integer(), server_default="0", nullable=False),
        sa.Column("corrupted_objects", sa.Integer(), server_default="0", nullable=False),
        sa.Column("missing_objects", sa.Integer(), server_default="0", nullable=False),
        sa.Column("duration_seconds", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("status", sa.String(length=30), server_default="RUNNING", nullable=False),
        sa.Column("details_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    )

    # 12. Create deletion_guards table
    op.create_table(
        "deletion_guards",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_type", sa.String(length=50), nullable=False),
        sa.Column("requester_id", sa.Integer(), nullable=True),
        sa.Column("requester_username", sa.String(length=100), nullable=False),
        sa.Column("target_resource_type", sa.String(length=50), nullable=False),
        sa.Column("target_resource_id", sa.String(length=100), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="PENDING", nullable=False),
        sa.Column("risk_score", sa.Integer(), server_default="50", nullable=False),
        sa.Column("approved_by", sa.String(length=100), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    )

    # 13. Create security_simulations table
    op.create_table(
        "security_simulations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("simulation_id", sa.String(length=50), unique=True, nullable=False),
        sa.Column("scenario_type", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="PENDING", nullable=False),
        sa.Column("sandbox_path", sa.String(length=500), nullable=False),
        sa.Column("parameters_json", sa.Text(), nullable=True),
        sa.Column("results_json", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_table("security_simulations")
    op.drop_table("deletion_guards")
    op.drop_table("integrity_scans")
    op.drop_table("configuration_drifts")
    op.drop_table("security_incidents")
    op.drop_table("security_events")
    op.drop_table("policy_versions")
    op.drop_table("client_groups")
    op.drop_table("security_profiles")
