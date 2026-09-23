import datetime
from typing import Optional, List
from sqlalchemy import Integer, String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

class BackupPolicy(Base):
    __tablename__ = "backup_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    backup_type: Mapped[str] = mapped_column(String(20), default="incremental", nullable=False)  # full, incremental
    change_detection: Mapped[str] = mapped_column(String(30), default="usn_journal", nullable=False)  # usn_journal, scheduled_scan
    rpo_target_seconds: Mapped[int] = mapped_column(Integer, default=120, nullable=False)
    compression_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    encryption_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    cpu_limit_percent: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    network_limit_mbps: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    retention_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    paths = relationship("BackupPolicyPath", back_populates="policy", cascade="all, delete-orphan")
    jobs = relationship("BackupJob", back_populates="policy")
    retention_policy = relationship("RetentionPolicy", back_populates="policy", uselist=False, cascade="all, delete-orphan")

class BackupPolicyPath(Base):
    __tablename__ = "backup_policy_paths"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    policy_id: Mapped[int] = mapped_column(Integer, ForeignKey("backup_policies.id", ondelete="CASCADE"), nullable=False, index=True)
    path_type: Mapped[str] = mapped_column(String(20), default="universal", nullable=False)  # universal, custom
    path_value: Mapped[str] = mapped_column(String(500), nullable=False)
    is_excluded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    policy = relationship("BackupPolicy", back_populates="paths")
