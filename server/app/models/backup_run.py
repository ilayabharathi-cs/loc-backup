import datetime
from typing import Optional, List
from sqlalchemy import Integer, BigInteger, String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

class BackupRun(Base):
    __tablename__ = "backup_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("backup_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id: Mapped[int] = mapped_column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    backup_type: Mapped[str] = mapped_column(String(20), default="incremental", nullable=False)  # full, incremental
    started_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running", nullable=False)  # running, completed, failed, cancelled
    files_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    files_discovered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    files_uploaded: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    files_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bytes_total: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    bytes_processed: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    bytes_uploaded: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    policy_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("backup_policies.id", ondelete="SET NULL"), nullable=True, index=True)

    job = relationship("BackupJob", back_populates="runs")
    client = relationship("Client", back_populates="runs")
    policy = relationship("BackupPolicy")
    files = relationship("BackupFile", back_populates="run", cascade="all, delete-orphan")
    recovery_points = relationship("RecoveryPoint", back_populates="run", cascade="all, delete-orphan")
