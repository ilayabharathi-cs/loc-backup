"""0004_v4_reliability

Revision ID: 3a8f9c123456
Revises: c8192a510123
Create Date: 2026-09-23 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '3a8f9c123456'
down_revision: Union[str, None] = 'c8192a510123'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update backup_runs
    with op.batch_alter_table("backup_runs") as batch_op:
        batch_op.add_column(sa.Column("state", sa.String(length=30), server_default="CREATED", nullable=False))
        batch_op.add_column(sa.Column("lease_id", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("interrupted_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("resumed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("checkpoint_version", sa.Integer(), server_default="1", nullable=False))
        batch_op.add_column(sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("files_locked", sa.Integer(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("files_vss_recovered", sa.Integer(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("files_skipped", sa.Integer(), server_default="0", nullable=False))

    # 2. Create upload_sessions
    op.create_table(
        "upload_sessions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("backup_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("object_id", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=1000), nullable=False),
        sa.Column("relative_path", sa.String(length=1000), nullable=True),
        sa.Column("change_type", sa.String(length=20), server_default="FULL", nullable=False),
        sa.Column("total_size", sa.BigInteger(), nullable=False),
        sa.Column("chunk_size", sa.Integer(), server_default="4194304", nullable=False),
        sa.Column("total_chunks", sa.Integer(), nullable=False),
        sa.Column("received_bytes", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("next_chunk_index", sa.Integer(), server_default="0", nullable=False),
        sa.Column("file_mtime", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expected_sha256", sa.String(length=64), nullable=True),
        sa.Column("final_sha256", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("staging_path", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index("ix_upload_sessions_id", "upload_sessions", ["id"])
    op.create_index("ix_upload_sessions_run_id", "upload_sessions", ["run_id"])

    # 3. Create upload_chunks
    op.create_table(
        "upload_chunks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("upload_session_id", sa.String(length=64), sa.ForeignKey("upload_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("offset", sa.BigInteger(), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="persisted", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("upload_session_id", "chunk_index", name="uq_session_chunk_index")
    )
    op.create_index("ix_upload_chunks_session_id", "upload_chunks", ["upload_session_id"])
    op.create_index("ix_upload_chunks_chunk_index", "upload_chunks", ["chunk_index"])

    # 4. Create backup_checkpoints
    op.create_table(
        "backup_checkpoints",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("backup_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("current_file", sa.String(length=1000), nullable=True),
        sa.Column("bytes_uploaded", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("last_chunk_index", sa.Integer(), server_default="0", nullable=False),
        sa.Column("state", sa.String(length=30), server_default="BACKING_UP", nullable=False),
        sa.Column("checkpoint_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    )
    op.create_index("ix_backup_checkpoints_run_id", "backup_checkpoints", ["run_id"])

    # 5. Create run_events
    op.create_table(
        "run_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("backup_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("message", sa.String(length=1000), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("event_metadata", sa.Text(), nullable=True)
    )
    op.create_index("ix_run_events_run_id", "run_events", ["run_id"])
    op.create_index("ix_run_events_event_type", "run_events", ["event_type"])


def downgrade() -> None:
    op.drop_table("run_events")
    op.drop_table("backup_checkpoints")
    op.drop_table("upload_chunks")
    op.drop_table("upload_sessions")

    with op.batch_alter_table("backup_runs") as batch_op:
        batch_op.drop_column("files_skipped")
        batch_op.drop_column("files_vss_recovered")
        batch_op.drop_column("files_locked")
        batch_op.drop_column("retry_count")
        batch_op.drop_column("checkpoint_version")
        batch_op.drop_column("resumed_at")
        batch_op.drop_column("interrupted_at")
        batch_op.drop_column("lease_expires_at")
        batch_op.drop_column("lease_id")
        batch_op.drop_column("state")
