import datetime
from typing import Optional, List
from sqlalchemy import Integer, BigInteger, String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class UploadSession(Base):
    __tablename__ = "upload_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)  # UUID session id
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("backup_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    object_id: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    relative_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    change_type: Mapped[str] = mapped_column(String(20), default="FULL", nullable=False)
    total_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    chunk_size: Mapped[int] = mapped_column(Integer, default=4194304, nullable=False)
    total_chunks: Mapped[int] = mapped_column(Integer, nullable=False)
    received_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    next_chunk_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    file_mtime: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expected_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    final_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)  # active, completed, aborted
    staging_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    run = relationship("BackupRun", back_populates="upload_sessions")
    chunks = relationship("UploadChunk", back_populates="session", cascade="all, delete-orphan", order_by="UploadChunk.chunk_index")
