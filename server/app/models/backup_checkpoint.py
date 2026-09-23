import datetime
from typing import Optional
from sqlalchemy import Integer, BigInteger, String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class BackupCheckpoint(Base):
    __tablename__ = "backup_checkpoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("backup_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id: Mapped[int] = mapped_column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    current_file: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    bytes_uploaded: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    last_chunk_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    state: Mapped[str] = mapped_column(String(30), default="BACKING_UP", nullable=False)
    checkpoint_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    run = relationship("BackupRun", back_populates="checkpoints")
    client = relationship("Client")
