import datetime
from typing import Optional, List
from sqlalchemy import Integer, BigInteger, String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

class BackupRun(Base):
    __tablename__ = "backup_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("backup_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id: Mapped[int] = mapped_column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    backup_type: Mapped[str] = mapped_column(String(20), default="incremental", nullable=False)  # full, incremental
    started_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running", nullable=False)  # running, completed, failed, cancelled
    state: Mapped[str] = mapped_column(String(30), default="CREATED", nullable=False)  # CREATED, DISCOVERING, SCANNING, BACKING_UP, PAUSED, INTERRUPTED, RESUMING, VERIFYING, COMPLETING, COMPLETED, FAILED, CANCELLED
    lease_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    lease_expires_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    interrupted_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resumed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    checkpoint_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    files_locked: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    files_vss_recovered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    files_skipped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    files_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    files_discovered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    files_uploaded: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    files_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    files_new: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    files_modified: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    files_unchanged: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    files_deleted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bytes_total: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    bytes_processed: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    bytes_uploaded: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    policy_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("backup_policies.id", ondelete="SET NULL"), nullable=True, index=True)
    baseline_run_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("backup_runs.id", ondelete="SET NULL"), nullable=True, index=True)

    job = relationship("BackupJob", back_populates="runs")
    client = relationship("Client", back_populates="runs")
    policy = relationship("BackupPolicy")
    files = relationship("BackupFile", back_populates="run", cascade="all, delete-orphan")
    recovery_points = relationship("RecoveryPoint", back_populates="run", cascade="all, delete-orphan")
    upload_sessions = relationship("UploadSession", back_populates="run", cascade="all, delete-orphan")
    checkpoints = relationship("BackupCheckpoint", back_populates="run", cascade="all, delete-orphan")
    events = relationship("RunEvent", back_populates="run", cascade="all, delete-orphan")
