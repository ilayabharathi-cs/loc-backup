"""0002_v2_full_backup_schema

Revision ID: b7490ac921f0
Revises: 839ffae71a8e
Create Date: 2026-09-22 23:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'b7490ac921f0'
down_revision: Union[str, None] = '839ffae71a8e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add columns to backup_runs
    with op.batch_alter_table("backup_runs") as batch_op:
        batch_op.add_column(sa.Column("policy_id", sa.Integer(), sa.ForeignKey("backup_policies.id", ondelete="SET NULL"), nullable=True))
        batch_op.add_column(sa.Column("files_discovered", sa.Integer(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("files_uploaded", sa.Integer(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("files_failed", sa.Integer(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("bytes_total", sa.BigInteger(), server_default="0", nullable=False))

    # Add columns to backup_files
    with op.batch_alter_table("backup_files") as batch_op:
        batch_op.add_column(sa.Column("relative_path", sa.String(length=1000), nullable=True))
        batch_op.add_column(sa.Column("upload_status", sa.String(length=50), server_default="completed", nullable=False))
        batch_op.add_column(sa.Column("modified_time", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("backup_files") as batch_op:
        batch_op.drop_column("modified_time")
        batch_op.drop_column("upload_status")
        batch_op.drop_column("relative_path")

    with op.batch_alter_table("backup_runs") as batch_op:
        batch_op.drop_column("bytes_total")
        batch_op.drop_column("files_failed")
        batch_op.drop_column("files_uploaded")
        batch_op.drop_column("files_discovered")
        batch_op.drop_column("policy_id")
