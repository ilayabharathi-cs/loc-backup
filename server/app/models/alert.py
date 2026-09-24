import datetime
from typing import Optional, List
from sqlalchemy import Integer, Boolean, String, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    rule_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # Types: BACKUP_FAILED, BACKUP_MISSED, AGENT_OFFLINE, REPOSITORY_OFFLINE, LOW_STORAGE, REPLICATION_FAILED, REPLICATION_LAG, CORRUPTED_OBJECT, RESTORE_FAILED, SECURITY_EVENT, RPO_BREACH
    severity: Mapped[str] = mapped_column(String(20), default="WARNING", nullable=False)  # INFO, WARNING, ERROR, CRITICAL
    threshold_value: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    alerts = relationship("Alert", back_populates="rule", cascade="all, delete-orphan")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    rule_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("alert_rules.id", ondelete="SET NULL"), nullable=True, index=True)
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), default="WARNING", nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False, index=True)  # ACTIVE, ACKNOWLEDGED, RESOLVED
    resource_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    acknowledged_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    rule = relationship("AlertRule", back_populates="alerts")


class NotificationChannel(Base):
    __tablename__ = "notification_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    channel_type: Mapped[str] = mapped_column(String(30), nullable=False)  # EMAIL, WEBHOOK
    target: Mapped[str] = mapped_column(String(500), nullable=False)  # Email address or Webhook URL
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    configuration: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON config e.g. headers, smtp settings
    cooldown_seconds: Mapped[int] = mapped_column(Integer, default=300, nullable=False)
    last_sent_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    channel_id: Mapped[int] = mapped_column(Integer, ForeignKey("notification_channels.id", ondelete="CASCADE"), nullable=False, index=True)
    alert_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("alerts.id", ondelete="SET NULL"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="SENT", nullable=False)  # SENT, FAILED, RETRYING
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sent_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
