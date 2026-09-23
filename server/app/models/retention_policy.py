"""Retention policy and evaluation models for GFS & lifecycle management (RetroVault V5)."""

import datetime
from typing import Optional, List
from sqlalchemy import Integer, BigInteger, String, Boolean, DateTime, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class RetentionPolicy(Base):
    """
    Retention & GFS policy configuring automated lifecycle management for Recovery Points.
    Supports keep-last count, daily, weekly, monthly, yearly GFS rules and timezone awareness.
    """
    __tablename__ = "retention_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    policy_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("backup_policies.id", ondelete="CASCADE"), nullable=True, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    keep_last: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    daily: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    weekly: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    monthly: Mapped[int] = mapped_column(Integer, default=12, nullable=False)
    yearly: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    policy = relationship("BackupPolicy", back_populates="retention_policy")
    evaluations = relationship("RetentionEvaluation", back_populates="retention_policy", cascade="all, delete-orphan")


class RetentionEvaluation(Base):
    """Logs the results of an automated retention and GFS evaluation run."""
    __tablename__ = "retention_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    retention_policy_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("retention_policies.id", ondelete="SET NULL"), nullable=True, index=True)
    evaluated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    total_recovery_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    protected_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expired_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reclaimed_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON summary of decisions

    retention_policy = relationship("RetentionPolicy", back_populates="evaluations")
