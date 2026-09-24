"""Database models for RetroVault V12 Cloud & Hybrid Storage Tiering."""

import datetime
from typing import Optional
from sqlalchemy import Integer, BigInteger, String, Boolean, DateTime, Text, ForeignKey, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class CloudCredential(Base):
    """
    Encrypted cloud credentials store.
    Access keys and secret keys are encrypted at rest using SecretManager.
    Plaintext secrets are never exposed via normal APIs, logs, or repr.
    """
    __tablename__ = "cloud_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    credential_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), unique=True, index=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), default="s3", nullable=False)  # s3, minio, wasabi, mock
    endpoint: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    region: Mapped[Optional[str]] = mapped_column(String(50), default="us-east-1", nullable=True)
    access_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    secret_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    prefix: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    use_tls: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    verify_ssl: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="configured", nullable=False)  # configured, verified, error, disabled
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    storage_tiers = relationship("StorageTier", back_populates="credential", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        # Never leak secret keys or raw credentials in repr
        return f"<CloudCredential id={self.id} credential_id='{self.credential_id}' name='{self.name}' provider='{self.provider}' status='{self.status}'>"


class StorageTier(Base):
    """
    Hybrid Storage Tier configuration representing local, S3, MinIO, or cloud targets.
    Coordinates lifecycle states: CREATED, VALIDATING, READY, DEGRADED, ERROR, DISABLED.
    """
    __tablename__ = "storage_tiers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tier_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), unique=True, index=True, nullable=False)
    tier_type: Mapped[str] = mapped_column(String(50), default="CLOUD_S3", nullable=False)  # HOT, WARM, COLD, ARCHIVE, CLOUD_S3
    provider: Mapped[str] = mapped_column(String(50), default="s3", nullable=False)  # s3, minio, wasabi, mock
    credential_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("cloud_credentials.id", ondelete="SET NULL"), nullable=True)
    bucket: Mapped[str] = mapped_column(String(255), nullable=False)
    prefix: Mapped[Optional[str]] = mapped_column(String(255), default="", nullable=True)
    state: Mapped[str] = mapped_column(String(50), default="CREATED", nullable=False, index=True)  # CREATED, VALIDATING, READY, DEGRADED, ERROR, DISABLED
    object_lock_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    retention_period_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    immutability_mode: Mapped[str] = mapped_column(String(50), default="NONE", nullable=False)  # NONE, GOVERNANCE, COMPLIANCE
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_validated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    credential = relationship("CloudCredential", back_populates="storage_tiers")
    offloaded_objects = relationship("CloudOffloadedObject", back_populates="storage_tier", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<StorageTier id={self.id} tier_id='{self.tier_id}' name='{self.name}' provider='{self.provider}' state='{self.state}'>"


class CloudOffloadedObject(Base):
    """
    Tracks offloaded CAS StorageObjects in cloud storage tiers.
    Ensures safe COPY -> VERIFY -> RECORD workflow while preserving local CAS authoritative state.
    """
    __tablename__ = "cloud_offloaded_objects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    offload_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    storage_tier_id: Mapped[int] = mapped_column(Integer, ForeignKey("storage_tiers.id", ondelete="CASCADE"), nullable=False, index=True)
    storage_object_id: Mapped[str] = mapped_column(String(64), ForeignKey("storage_objects.object_id", ondelete="RESTRICT"), nullable=False, index=True)
    remote_key: Mapped[str] = mapped_column(String(500), nullable=False)
    remote_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    remote_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    state: Mapped[str] = mapped_column(String(50), default="OFFLOADED", nullable=False, index=True)  # PENDING, OFFLOADED, VERIFIED, FAILED, RESTORED
    verification_status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False)  # PENDING, VERIFIED, FAILED
    verified_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    offloaded_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    offloaded_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    etag: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    object_lock_until: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    storage_tier = relationship("StorageTier", back_populates="offloaded_objects")
    storage_object = relationship("StorageObject")

    __table_args__ = (
        Index("ix_cloud_offload_tier_obj", "storage_tier_id", "storage_object_id"),
    )

    def __repr__(self) -> str:
        return f"<CloudOffloadedObject id={self.id} offload_id='{self.offload_id}' storage_object_id='{self.storage_object_id}' state='{self.state}'>"
