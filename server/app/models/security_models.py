import datetime
from typing import Optional
from sqlalchemy import Integer, BigInteger, Float, Boolean, String, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class AgentCredential(Base):
    __tablename__ = "agent_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", nullable=False, index=True)  # ACTIVE, PENDING_CONFIRMATION, REVOKED
    issued_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    confirmed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rotation_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    client = relationship("Client")


class MfaSetting(Base):
    __tablename__ = "mfa_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    secret_encrypted: Mapped[str] = mapped_column(String(500), nullable=False)
    recovery_codes_hash: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array of hashed recovery codes
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    enrolled_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_verified_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User")


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # Categories: general, server, repositories, security, agents, backup, retention, replication, notifications, audit, dr
    key: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)  # JSON or scalar value as string
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    updated_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)


class DrTest(Base):
    __tablename__ = "dr_tests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    test_id: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    recovery_point_id: Mapped[int] = mapped_column(Integer, ForeignKey("recovery_points.id", ondelete="CASCADE"), nullable=False, index=True)
    target_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    files_tested: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bytes_tested: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    files_verified: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    result: Mapped[str] = mapped_column(String(30), default="PASSED", nullable=False, index=True)  # PASSED, FAILED, PARTIAL
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    recovery_point = relationship("RecoveryPoint")
