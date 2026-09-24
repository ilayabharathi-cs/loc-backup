import datetime
from typing import Optional, List
from sqlalchemy import Integer, BigInteger, Float, String, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class ReplicationJob(Base):
    __tablename__ = "replication_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    source_repository_id: Mapped[int] = mapped_column(Integer, ForeignKey("storage_repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    destination_repository_id: Mapped[int] = mapped_column(Integer, ForeignKey("storage_repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    recovery_point_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("recovery_points.id", ondelete="SET NULL"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="CREATED", nullable=False, index=True)
    # Statuses: CREATED, PLANNING, QUEUED, RUNNING, PAUSED, INTERRUPTED, RESUMING, VERIFYING, COMPLETED, PARTIAL, FAILED, CANCELLED

    total_objects: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_objects: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_objects: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_objects: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    total_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    transferred_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    bandwidth_limit_mbps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    progress_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    started_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    source_repository = relationship("StorageRepository", foreign_keys=[source_repository_id])
    destination_repository = relationship("StorageRepository", foreign_keys=[destination_repository_id])
    recovery_point = relationship("RecoveryPoint")
    items = relationship("ReplicationItem", back_populates="job", cascade="all, delete-orphan")
    checkpoints = relationship("ReplicationCheckpoint", back_populates="job", cascade="all, delete-orphan")


class ReplicationItem(Base):
    __tablename__ = "replication_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("replication_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    storage_object_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("storage_objects.id", ondelete="SET NULL"), nullable=True, index=True)
    source_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    destination_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    stored_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    stored_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="PENDING", nullable=False, index=True)
    # Statuses: PENDING, IN_PROGRESS, VERIFIED, COMPLETED, SKIPPED, FAILED
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    transferred_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    job = relationship("ReplicationJob", back_populates="items")
    storage_object = relationship("StorageObject")


class ReplicationCheckpoint(Base):
    __tablename__ = "replication_checkpoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("replication_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    last_completed_item_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completed_objects: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    transferred_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    checkpoint_state: Mapped[str] = mapped_column(String(50), default="ACTIVE", nullable=False)
    recorded_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    job = relationship("ReplicationJob", back_populates="checkpoints")
