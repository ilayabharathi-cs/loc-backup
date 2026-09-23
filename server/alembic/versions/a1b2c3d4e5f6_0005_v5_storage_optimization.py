"""0005_v5_storage_optimization

Revision ID: a1b2c3d4e5f6
Revises: 3a8f9c123456
Create Date: 2026-09-23 13:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '3a8f9c123456'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create storage_objects
    op.create_table(
        "storage_objects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("object_id", sa.String(length=64), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("stored_sha256", sa.String(length=64), nullable=False),
        sa.Column("original_size", sa.BigInteger(), nullable=False),
        sa.Column("stored_size", sa.BigInteger(), nullable=False),
        sa.Column("compression_algorithm", sa.String(length=20), server_default="NONE", nullable=False),
        sa.Column("compression_ratio", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("encryption_status", sa.String(length=20), server_default="NONE", nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("reference_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("state", sa.String(length=20), server_default="AVAILABLE", nullable=False),
        sa.Column("integrity_status", sa.String(length=20), server_default="VALID", nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    )
    op.create_index("ix_storage_objects_id", "storage_objects", ["id"])
    op.create_index("ix_storage_objects_object_id", "storage_objects", ["object_id"], unique=True)
    op.create_index("ix_storage_objects_content_sha256", "storage_objects", ["content_sha256"])
    op.create_index("ix_storage_objects_stored_sha256", "storage_objects", ["stored_sha256"])
    op.create_index("ix_storage_objects_state", "storage_objects", ["state"])
    op.create_index("ix_storage_objects_reference_count", "storage_objects", ["reference_count"])
    op.create_index("idx_storage_obj_content_sha", "storage_objects", ["content_sha256"])
    op.create_index("idx_storage_obj_state_ref", "storage_objects", ["state", "reference_count"])

    # 2. Update backup_files with storage_object_id
    with op.batch_alter_table("backup_files") as batch_op:
        batch_op.add_column(sa.Column("storage_object_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_backup_files_storage_object", "storage_objects", ["storage_object_id"], ["id"], ondelete="SET NULL")
        batch_op.create_index("ix_backup_files_storage_object_id", ["storage_object_id"])

    # 3. Update recovery_points with retention and GFS fields
    with op.batch_alter_table("recovery_points") as batch_op:
        batch_op.add_column(sa.Column("retention_status", sa.String(length=20), server_default="active", nullable=False))
        batch_op.add_column(sa.Column("is_daily", sa.Boolean(), server_default=sa.false(), nullable=False))
        batch_op.add_column(sa.Column("is_weekly", sa.Boolean(), server_default=sa.false(), nullable=False))
        batch_op.add_column(sa.Column("is_monthly", sa.Boolean(), server_default=sa.false(), nullable=False))
        batch_op.add_column(sa.Column("is_yearly", sa.Boolean(), server_default=sa.false(), nullable=False))
        batch_op.add_column(sa.Column("is_manual_protected", sa.Boolean(), server_default=sa.false(), nullable=False))
        batch_op.add_column(sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("retention_tier", sa.String(length=20), nullable=True))
        batch_op.create_index("ix_recovery_points_retention_status", ["retention_status"])

    # 4. Create retention_policies
    op.create_table(
        "retention_policies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("policy_id", sa.Integer(), sa.ForeignKey("backup_policies.id", ondelete="CASCADE"), nullable=True, unique=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("keep_last", sa.Integer(), server_default="10", nullable=False),
        sa.Column("daily", sa.Integer(), server_default="7", nullable=False),
        sa.Column("weekly", sa.Integer(), server_default="4", nullable=False),
        sa.Column("monthly", sa.Integer(), server_default="12", nullable=False),
        sa.Column("yearly", sa.Integer(), server_default="7", nullable=False),
        sa.Column("timezone", sa.String(length=50), server_default="UTC", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    )
    op.create_index("ix_retention_policies_id", "retention_policies", ["id"])

    # 5. Create retention_evaluations
    op.create_table(
        "retention_evaluations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("retention_policy_id", sa.Integer(), sa.ForeignKey("retention_policies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("total_recovery_points", sa.Integer(), server_default="0", nullable=False),
        sa.Column("protected_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("expired_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("reclaimed_bytes", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("details", sa.Text(), nullable=True)
    )
    op.create_index("ix_retention_evaluations_id", "retention_evaluations", ["id"])
    op.create_index("ix_retention_evaluations_retention_policy_id", "retention_evaluations", ["retention_policy_id"])

    # 6. Create garbage_collection_jobs
    op.create_table(
        "garbage_collection_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("candidates_found", sa.Integer(), server_default="0", nullable=False),
        sa.Column("objects_deleted", sa.Integer(), server_default="0", nullable=False),
        sa.Column("objects_skipped", sa.Integer(), server_default="0", nullable=False),
        sa.Column("bytes_reclaimed", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    )
    op.create_index("ix_garbage_collection_jobs_id", "garbage_collection_jobs", ["id"])
    op.create_index("ix_garbage_collection_jobs_job_id", "garbage_collection_jobs", ["job_id"], unique=True)

    # 7. Create garbage_collection_items
    op.create_table(
        "garbage_collection_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("gc_job_id", sa.Integer(), sa.ForeignKey("garbage_collection_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("storage_object_id", sa.Integer(), sa.ForeignKey("storage_objects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("object_sha256", sa.String(length=64), nullable=False),
        sa.Column("stored_size", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="marked", nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    )
    op.create_index("ix_garbage_collection_items_id", "garbage_collection_items", ["id"])
    op.create_index("ix_garbage_collection_items_gc_job_id", "garbage_collection_items", ["gc_job_id"])
    op.create_index("ix_garbage_collection_items_storage_object_id", "garbage_collection_items", ["storage_object_id"])
    op.create_index("idx_gc_item_job_obj", "garbage_collection_items", ["gc_job_id", "storage_object_id"])


def downgrade() -> None:
    op.drop_table("garbage_collection_items")
    op.drop_table("garbage_collection_jobs")
    op.drop_table("retention_evaluations")
    op.drop_table("retention_policies")
    with op.batch_alter_table("recovery_points") as batch_op:
        batch_op.drop_column("retention_tier")
        batch_op.drop_column("expires_at")
        batch_op.drop_column("is_manual_protected")
        batch_op.drop_column("is_yearly")
        batch_op.drop_column("is_monthly")
        batch_op.drop_column("is_weekly")
        batch_op.drop_column("is_daily")
        batch_op.drop_column("retention_status")
    with op.batch_alter_table("backup_files") as batch_op:
        batch_op.drop_column("storage_object_id")
    op.drop_table("storage_objects")
