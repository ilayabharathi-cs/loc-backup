import datetime
from typing import Optional
from sqlalchemy import Integer, BigInteger, String, Boolean, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base

class StorageRepository(Base):
    __tablename__ = "storage_repositories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    repository_type: Mapped[str] = mapped_column(String(50), default="LOCAL_FILESYSTEM", nullable=False)  # LOCAL_FILESYSTEM, REMOTE_FILESYSTEM, S3_COMPATIBLE
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    endpoint: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    root_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    total_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    used_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    available_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="ONLINE", nullable=False)  # ONLINE, DEGRADED, OFFLINE, READ_ONLY, ERROR, MAINTENANCE
    protection_mode: Mapped[str] = mapped_column(String(20), default="NORMAL", nullable=False)  # NORMAL, PROTECTED, IMMUTABLE
    immutability_state: Mapped[str] = mapped_column(String(30), default="DISABLED", nullable=False)  # DISABLED, SOFT_IMMUTABLE, RETENTION_LOCKED, WORM, OBJECT_LOCK
    capabilities_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    encryption_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_health_check: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    configuration: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    @property
    def capacity_bytes(self) -> int:
        return self.total_bytes

    @capacity_bytes.setter
    def capacity_bytes(self, value: int):
        self.total_bytes = value

    @property
    def effective_root_path(self) -> str:
        return self.root_path or self.path
