import datetime
from typing import Optional
from sqlalchemy import Integer, BigInteger, String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

class RecoveryPoint(Base):
    __tablename__ = "recovery_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    backup_run_id: Mapped[int] = mapped_column(Integer, ForeignKey("backup_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    backup_type: Mapped[Optional[str]] = mapped_column(String(20), default="full", nullable=True)
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    files_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_size_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="valid", nullable=False)  # valid, corrupted, pruned, expired

    # V5 Retention & GFS Fields
    retention_status: Mapped[str] = mapped_column(String(20), default="active", nullable=False, index=True)  # active, protected, expired, pruned
    is_daily: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_weekly: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_monthly: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_yearly: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_manual_protected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    retention_tier: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # DAILY, WEEKLY, MONTHLY, YEARLY, KEEP_LAST

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    client = relationship("Client", back_populates="recovery_points")
    run = relationship("BackupRun", back_populates="recovery_points")
    restore_jobs = relationship("RestoreJob", back_populates="recovery_point")
