import datetime
from typing import Optional
from sqlalchemy import Integer, BigInteger, String, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

class RestoreCheckpoint(Base):
    __tablename__ = "restore_checkpoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    restore_job_id: Mapped[int] = mapped_column(Integer, ForeignKey("restore_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    last_completed_item_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completed_items_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bytes_restored: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    checkpoint_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON metadata string
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    restore_job = relationship("RestoreJob", back_populates="checkpoints")
