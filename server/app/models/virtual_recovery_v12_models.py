"""Database models for RetroVault V12 Instant Virtual Recovery."""

import datetime
from typing import Optional, List
from sqlalchemy import Integer, BigInteger, String, Boolean, Float, DateTime, Text, ForeignKey, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class VirtualRecoverySession(Base):
    """
    Manages an Instant Virtual Recovery session.
    Enables instant access to a valid Recovery Point without waiting for physical data copy.
    Coordinates on-demand reads, bounded cache, and background hydration.
    """
    __tablename__ = "virtual_recovery_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    recovery_point_id: Mapped[int] = mapped_column(Integer, ForeignKey("recovery_points.id", ondelete="RESTRICT"), nullable=False, index=True)
    client_id: Mapped[int] = mapped_column(Integer, ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False, index=True)
    workload_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    target_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    mount_point: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    provider_type: Mapped[str] = mapped_column(String(50), default="LOCAL_VIRTUAL", nullable=False)
    cloud_tier_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("storage_tiers.id", ondelete="SET NULL"), nullable=True)

    # State machine: CREATED, PREPARING, MOUNTING, READY, DEGRADED, PAUSED, HYDRATING, COMPLETING, COMPLETED, FAILED, CANCELLED, UNMOUNTING
    state: Mapped[str] = mapped_column(String(50), default="CREATED", nullable=False, index=True)
    hydration_status: Mapped[str] = mapped_column(String(50), default="NOT_STARTED", nullable=False)  # NOT_STARTED, RUNNING, PAUSED, COMPLETED, FAILED

    total_files: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    hydrated_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    hydrated_files: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hydration_speed_bps: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    hydration_eta_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    read_requests_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bytes_read: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    cache_hits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cache_misses: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cache_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    # RTO Telemetry
    time_to_first_access_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    time_to_app_ready_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    time_to_full_hydration_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_details_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    session_metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    prepared_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    mounted_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    first_access_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    app_ready_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    hydration_started_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    unmounted_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    recovery_point = relationship("RecoveryPoint")
    client = relationship("Client")
    storage_tier = relationship("StorageTier")
    hydration_items = relationship("VirtualRecoveryHydrationItem", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<VirtualRecoverySession id={self.id} session_id='{self.session_id}' state='{self.state}'>"


class VirtualRecoveryHydrationItem(Base):
    """
    Tracks individual file hydration progress within an Instant Virtual Recovery session.
    """
    __tablename__ = "virtual_recovery_hydration_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("virtual_recovery_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    relative_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    storage_object_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="PENDING", nullable=False)  # PENDING, FETCHING, HYDRATED, FAILED
    fetch_source: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)  # LOCAL_CAS, CLOUD_TIER, CACHE
    hydrated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    session = relationship("VirtualRecoverySession", back_populates="hydration_items")

    __table_args__ = (
        Index("ix_vrec_item_session_path", "session_id", "relative_path"),
    )
