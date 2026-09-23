import datetime
from typing import Optional
from sqlalchemy import Integer, BigInteger, String, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

class RestoreItem(Base):
    __tablename__ = "restore_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    restore_job_id: Mapped[int] = mapped_column(Integer, ForeignKey("restore_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    backup_file_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("backup_files.id", ondelete="SET NULL"), nullable=True, index=True)
    relative_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    destination_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_size: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    restored_size: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    source_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    restored_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False, index=True)  # PENDING, RESTORING, VERIFYING, COMPLETED, SKIPPED, FAILED, CANCELLED
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    restore_job = relationship("RestoreJob", back_populates="items")
    backup_file = relationship("BackupFile")
