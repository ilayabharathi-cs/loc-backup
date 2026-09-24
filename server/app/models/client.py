import datetime
from typing import Optional, List
from sqlalchemy import Integer, String, DateTime, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    hostname: Mapped[str] = mapped_column(String(100), nullable=False)
    device_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    os: Mapped[str] = mapped_column(String(50), nullable=False)
    os_version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ip_address: Mapped[str] = mapped_column(String(50), nullable=False)
    agent_version: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)  # pending, active, offline, disabled
    last_seen: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # V8 Fleet & Policy Orchestration
    group_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("client_groups.id", ondelete="SET NULL"), nullable=True, index=True)
    policy_override_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("backup_policies.id", ondelete="SET NULL"), nullable=True)
    effective_policy_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    group = relationship("ClientGroup", back_populates="clients")
    policy_override = relationship("BackupPolicy", foreign_keys=[policy_override_id])
    jobs = relationship("BackupJob", back_populates="client", cascade="all, delete-orphan")
    runs = relationship("BackupRun", back_populates="client", cascade="all, delete-orphan")
    files = relationship("BackupFile", back_populates="client", cascade="all, delete-orphan")
    recovery_points = relationship("RecoveryPoint", back_populates="client", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="client")

    @property
    def last_heartbeat(self) -> Optional[datetime.datetime]:
        return self.last_seen
