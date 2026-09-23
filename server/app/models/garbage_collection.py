"""Garbage Collection models for safe two-phase physical object cleanup (RetroVault V5)."""

import datetime
from typing import Optional, List
from sqlalchemy import Integer, BigInteger, String, DateTime, ForeignKey, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class GarbageCollectionJob(Base):
    """Tracks two-phase garbage collection executions and storage reclamation."""
    __tablename__ = "garbage_collection_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)  # pending, running, completed, failed, cancelled
    candidates_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    objects_deleted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    objects_skipped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bytes_reclaimed: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    started_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    items = relationship("GarbageCollectionItem", back_populates="gc_job", cascade="all, delete-orphan")


class GarbageCollectionItem(Base):
    """Individual storage object evaluated during a garbage collection pass."""
    __tablename__ = "garbage_collection_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    gc_job_id: Mapped[int] = mapped_column(Integer, ForeignKey("garbage_collection_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    storage_object_id: Mapped[int] = mapped_column(Integer, ForeignKey("storage_objects.id", ondelete="CASCADE"), nullable=False, index=True)
    object_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    stored_size: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="marked", nullable=False)  # marked, deleting, deleted, skipped, failed
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    gc_job = relationship("GarbageCollectionJob", back_populates="items")
    storage_obj = relationship("StorageObject", back_populates="gc_items")

    __table_args__ = (
        Index("idx_gc_item_job_obj", "gc_job_id", "storage_object_id"),
    )
