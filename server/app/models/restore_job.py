import datetime
from typing import Optional, List
from sqlalchemy import Integer, BigInteger, Float, String, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

class RestoreJob(Base):
    __tablename__ = "restore_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    restore_id: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    source_client_id: Mapped[int] = mapped_column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    target_client_id: Mapped[int] = mapped_column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    recovery_point_id: Mapped[int] = mapped_column(Integer, ForeignKey("recovery_points.id", ondelete="CASCADE"), nullable=False, index=True)
    source_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    target_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="CREATED", nullable=False, index=True)
    # Statuses: CREATED, VALIDATING, PLANNING, QUEUED, RUNNING, PAUSED, INTERRUPTED, RESUMING, VERIFYING, COMPLETING, COMPLETED, PARTIAL, FAILED, CANCELLED
    requested_by: Mapped[str] = mapped_column(String(100), nullable=False)

    # V6 Restore & Disaster Recovery Fields
    restore_mode: Mapped[str] = mapped_column(String(30), default="FULL_RECOVERY_POINT", nullable=False)  # FILE, FOLDER, SELECTION, FULL_RECOVERY_POINT
    conflict_mode: Mapped[str] = mapped_column(String(20), default="OVERWRITE", nullable=False)  # SKIP, OVERWRITE, RENAME, FAIL
    metadata_mode: Mapped[str] = mapped_column(String(20), default="BASIC", nullable=False)  # NONE, BASIC, FULL

    total_files: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_files: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_files: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_files: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    total_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    restored_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    verified_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    progress_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    started_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    restore_requested_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    first_byte_restored_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True)

    source_client = relationship("Client", foreign_keys=[source_client_id])
    target_client = relationship("Client", foreign_keys=[target_client_id])
    recovery_point = relationship("RecoveryPoint", back_populates="restore_jobs")
    items = relationship("RestoreItem", back_populates="restore_job", cascade="all, delete-orphan")
    checkpoints = relationship("RestoreCheckpoint", back_populates="restore_job", cascade="all, delete-orphan")

    @property
    def destination_client_id(self) -> int:
        return self.target_client_id

    @property
    def destination_path(self) -> str:
        return self.target_path
