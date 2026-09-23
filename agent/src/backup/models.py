"""Data models for RetroVault Backup Engine V2."""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import datetime


class BackupType(str, Enum):
    """Supported backup types in RetroVault."""
    FULL = "full"
    INCREMENTAL = "incremental"  # Architecture placeholder for V3


@dataclass
class DiscoveredFile:
    """Represents a file discovered during directory scan."""
    original_path: str
    relative_path: str
    file_name: str
    size_bytes: int
    modified_time: float
    created_time: Optional[float] = None
    is_accessible: bool = True
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_path": self.original_path,
            "relative_path": self.relative_path,
            "file_name": self.file_name,
            "size_bytes": self.size_bytes,
            "modified_time": self.modified_time,
            "created_time": self.created_time,
            "is_accessible": self.is_accessible,
            "error_message": self.error_message,
        }


@dataclass
class FileUploadResult:
    """Result of an individual file upload operation."""
    file_name: str
    original_path: str
    size_bytes: int
    sha256: Optional[str] = None
    storage_object: Optional[str] = None
    status: str = "uploaded"  # uploaded, failed, changed_during_backup, locked, interrupted
    error_message: Optional[str] = None
    retries: int = 0


@dataclass
class BackupProgress:
    """Live progress telemetry of an ongoing backup run."""
    run_id: int
    backup_type: str = "full"
    state: str = "BACKING_UP"
    files_discovered: int = 0
    files_uploaded: int = 0
    files_failed: int = 0
    files_new: int = 0
    files_modified: int = 0
    files_unchanged: int = 0
    files_deleted: int = 0
    files_locked: int = 0
    files_vss_recovered: int = 0
    files_skipped: int = 0
    bytes_total: int = 0
    bytes_uploaded: int = 0
    current_file: Optional[str] = None
    speed_mbps: float = 0.0

    @property
    def percent_complete(self) -> int:
        if self.bytes_total <= 0:
            return 100 if (self.files_discovered > 0 and self.files_uploaded == self.files_discovered) else 0
        return min(100, int((self.bytes_uploaded / self.bytes_total) * 100))


@dataclass
class BackupRunSummary:
    """Final summary of a backup run execution."""
    run_id: int
    client_id: str
    status: str  # completed, failed, cancelled, completed_with_warnings
    files_discovered: int
    files_uploaded: int
    files_failed: int
    bytes_total: int
    bytes_uploaded: int
    duration_seconds: float
    backup_type: str = "full"
    state: str = "COMPLETED"
    files_new: int = 0
    files_modified: int = 0
    files_unchanged: int = 0
    files_deleted: int = 0
    files_locked: int = 0
    files_vss_recovered: int = 0
    files_skipped: int = 0
    recovery_point_created: bool = False
    checkpoint_saved: bool = False
    error_message: Optional[str] = None
