"""0006_v6_restore_disaster_recovery

Revision ID: b1c2d3e4f5a6
Revises: a1b2c3d4e5f6
Create Date: 2026-09-23 14:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add V6 columns to restore_jobs
    with op.batch_alter_table("restore_jobs") as batch_op:
        batch_op.add_column(sa.Column("restore_mode", sa.String(length=30), server_default="FULL_RECOVERY_POINT", nullable=False))
        batch_op.add_column(sa.Column("conflict_mode", sa.String(length=20), server_default="OVERWRITE", nullable=False))
        batch_op.add_column(sa.Column("metadata_mode", sa.String(length=20), server_default="BASIC", nullable=False))
        batch_op.add_column(sa.Column("total_files", sa.Integer(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("completed_files", sa.Integer(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("failed_files", sa.Integer(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("skipped_files", sa.Integer(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("total_bytes", sa.BigInteger(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("restored_bytes", sa.BigInteger(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("verified_bytes", sa.BigInteger(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("progress_percent", sa.Float(), server_default="0.0", nullable=False))
        batch_op.add_column(sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("restore_requested_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("first_byte_restored_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("error_message", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))

    # 2. Create restore_items table
    op.create_table(
        "restore_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("restore_job_id", sa.Integer(), sa.ForeignKey("restore_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("backup_file_id", sa.Integer(), sa.ForeignKey("backup_files.id", ondelete="SET NULL"), nullable=True),
        sa.Column("relative_path", sa.String(length=1000), nullable=False),
        sa.Column("destination_path", sa.String(length=1000), nullable=False),
        sa.Column("source_size", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("restored_size", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("source_sha256", sa.String(length=64), nullable=True),
        sa.Column("restored_sha256", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="PENDING", nullable=False),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_code", sa.String(length=50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_restore_items_id", "restore_items", ["id"])
    op.create_index("ix_restore_items_restore_job_id", "restore_items", ["restore_job_id"])
    op.create_index("ix_restore_items_backup_file_id", "restore_items", ["backup_file_id"])
    op.create_index("ix_restore_items_status", "restore_items", ["status"])

    # 3. Create restore_checkpoints table
    op.create_table(
        "restore_checkpoints",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("restore_job_id", sa.Integer(), sa.ForeignKey("restore_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("last_completed_item_id", sa.Integer(), nullable=True),
        sa.Column("completed_items_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("bytes_restored", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("checkpoint_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_restore_checkpoints_id", "restore_checkpoints", ["id"])
    op.create_index("ix_restore_checkpoints_restore_job_id", "restore_checkpoints", ["restore_job_id"])


def downgrade() -> None:
    op.drop_table("restore_checkpoints")
    op.drop_table("restore_items")
    with op.batch_alter_table("restore_jobs") as batch_op:
        batch_op.drop_column("updated_at")
        batch_op.drop_column("error_message")
        batch_op.drop_column("first_byte_restored_at")
        batch_op.drop_column("restore_requested_at")
        batch_op.drop_column("cancelled_at")
        batch_op.drop_column("progress_percent")
        batch_op.drop_column("verified_bytes")
        batch_op.drop_column("restored_bytes")
        batch_op.drop_column("total_bytes")
        batch_op.drop_column("skipped_files")
        batch_op.drop_column("failed_files")
        batch_op.drop_column("completed_files")
        batch_op.drop_column("total_files")
        batch_op.drop_column("metadata_mode")
        batch_op.drop_column("conflict_mode")
        batch_op.drop_column("restore_mode")
