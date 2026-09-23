import datetime
from typing import Optional
from sqlalchemy import Integer, BigInteger, String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

class BackupFile(Base):
    __tablename__ = "backup_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    original_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    relative_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    backup_run_id: Mapped[int] = mapped_column(Integer, ForeignKey("backup_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    storage_object: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # V5 Content-Addressed Storage Reference
    storage_object_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("storage_objects.id", ondelete="SET NULL"), nullable=True, index=True)
    upload_status: Mapped[str] = mapped_column(String(50), default="completed", nullable=False)
    change_type: Mapped[str] = mapped_column(String(20), default="FULL", nullable=False)
    modified_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    client = relationship("Client", back_populates="files")
    run = relationship("BackupRun", back_populates="files")
    storage_obj = relationship("StorageObject", back_populates="backup_files")
