"""0003_v3_incremental_backup_schema

Revision ID: c8192a510123
Revises: b7490ac921f0
Create Date: 2026-09-23 11:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'c8192a510123'
down_revision: Union[str, None] = 'b7490ac921f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update backup_runs
    with op.batch_alter_table("backup_runs") as batch_op:
        batch_op.add_column(sa.Column("files_new", sa.Integer(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("files_modified", sa.Integer(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("files_unchanged", sa.Integer(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("files_deleted", sa.Integer(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("baseline_run_id", sa.Integer(), sa.ForeignKey("backup_runs.id", ondelete="SET NULL"), nullable=True))

    # 2. Update backup_files
    with op.batch_alter_table("backup_files") as batch_op:
        batch_op.add_column(sa.Column("change_type", sa.String(length=20), server_default="FULL", nullable=False))
        batch_op.alter_column("sha256", existing_type=sa.String(length=64), nullable=True)

    # 3. Update backup_jobs
    with op.batch_alter_table("backup_jobs") as batch_op:
        batch_op.add_column(sa.Column("backup_type", sa.String(length=20), server_default="full", nullable=False))

    # 4. Update recovery_points
    with op.batch_alter_table("recovery_points") as batch_op:
        batch_op.add_column(sa.Column("backup_type", sa.String(length=20), server_default="full", nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("recovery_points") as batch_op:
        batch_op.drop_column("backup_type")

    with op.batch_alter_table("backup_jobs") as batch_op:
        batch_op.drop_column("backup_type")

    with op.batch_alter_table("backup_files") as batch_op:
        batch_op.drop_column("change_type")
        batch_op.alter_column("sha256", existing_type=sa.String(length=64), nullable=False)

    with op.batch_alter_table("backup_runs") as batch_op:
        batch_op.drop_column("baseline_run_id")
        batch_op.drop_column("files_deleted")
        batch_op.drop_column("files_unchanged")
        batch_op.drop_column("files_modified")
        batch_op.drop_column("files_new")
