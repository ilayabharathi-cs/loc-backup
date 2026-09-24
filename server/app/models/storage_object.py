"""Storage Object model for Content-Addressed Storage & Deduplication (RetroVault V5)."""

import datetime
from typing import Optional, List
from sqlalchemy import Integer, BigInteger, String, Float, DateTime, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class StorageObject(Base):
    """
    Physical immutable content-addressed storage object in the repository.
    Uniquely identified by original content SHA-256 hash.
    Multiple logical BackupFiles across different runs, policies, and clients
    can reference a single StorageObject.
    """
    __tablename__ = "storage_objects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    object_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    stored_sha256: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    original_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    stored_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    compression_algorithm: Mapped[str] = mapped_column(String(20), default="NONE", nullable=False)  # NONE, ZSTD, GZIP
    compression_ratio: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    encryption_status: Mapped[str] = mapped_column(String(20), default="NONE", nullable=False)  # NONE, AES256_GCM
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)  # e.g. objects/d9/4a/d94abc...
    reference_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(20), default="AVAILABLE", nullable=False, index=True)  # AVAILABLE, VERIFYING, CORRUPTED, DELETING, DELETED, QUARANTINED
    integrity_status: Mapped[str] = mapped_column(String(20), default="VALID", nullable=False)  # VALID, CORRUPTED, UNVERIFIED
    verified_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    quarantined_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    quarantine_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    backup_files = relationship("BackupFile", back_populates="storage_obj")
    gc_items = relationship("GarbageCollectionItem", back_populates="storage_obj")

    @property
    def size_bytes(self) -> int:
        return self.stored_size

    __table_args__ = (
        Index("idx_storage_obj_content_sha", "content_sha256"),
        Index("idx_storage_obj_state_ref", "state", "reference_count"),
    )
