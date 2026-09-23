import datetime
from sqlalchemy import Integer, BigInteger, String, DateTime, ForeignKey, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class UploadChunk(Base):
    __tablename__ = "upload_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    upload_session_id: Mapped[str] = mapped_column(String(64), ForeignKey("upload_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    offset: Mapped[int] = mapped_column(BigInteger, nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="persisted", nullable=False)  # persisted, failed
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("upload_session_id", "chunk_index", name="uq_session_chunk_index"),
    )

    session = relationship("UploadSession", back_populates="chunks")
