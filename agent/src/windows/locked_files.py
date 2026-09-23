"""Locked and in-use file detection, classification, and safe reading for RetroVault V4."""

import os
import time
from enum import Enum
from typing import Optional, Tuple
from dataclasses import dataclass
from agent.src.windows.vss import VSSProvider
from agent.src.logger import get_logger


class FileLockState(str, Enum):
    READABLE = "READABLE"
    LOCKED = "LOCKED"
    CHANGED_DURING_READ = "CHANGED_DURING_READ"
    ACCESS_DENIED = "ACCESS_DENIED"
    NOT_FOUND = "NOT_FOUND"
    VSS_READABLE = "VSS_READABLE"


@dataclass
class FileInspectionResult:
    state: FileLockState
    effective_path: str
    size_bytes: int
    modified_time: float
    error_message: Optional[str] = None
    is_vss_used: bool = False


class LockedFileHandler:
    """Handles open, locked, and concurrently modified files with VSS fallback."""

    def __init__(self, vss_provider: Optional[VSSProvider] = None):
        self.vss_provider = vss_provider
        self.logger = get_logger()

    def inspect_file(
        self,
        original_path: str,
        relative_path: Optional[str] = None
    ) -> FileInspectionResult:
        """
        Inspect file accessibility, detect if locked by another process,
        and attempt VSS snapshot resolution if available.
        """
        if not os.path.exists(original_path):
            return FileInspectionResult(
                state=FileLockState.NOT_FOUND,
                effective_path=original_path,
                size_bytes=0,
                modified_time=0.0,
                error_message="File does not exist"
            )

        # 1. Test live file read access
        try:
            st = os.stat(original_path)
            with open(original_path, "rb") as f:
                # Read 1 byte to verify no exclusive sharing lock
                f.read(1)

            return FileInspectionResult(
                state=FileLockState.READABLE,
                effective_path=original_path,
                size_bytes=st.st_size,
                modified_time=st.st_mtime,
                is_vss_used=False
            )
        except PermissionError as e:
            # File locked or access denied
            self.logger.warning(f"File locked or access denied: '{original_path}': {e}")

            # 2. Try VSS snapshot if enabled
            if self.vss_provider and relative_path:
                drive, _ = os.path.splitdrive(original_path)
                vss_path = self.vss_provider.get_snapshot_path(drive or "C:", relative_path)
                if vss_path and os.path.exists(vss_path):
                    try:
                        vss_st = os.stat(vss_path)
                        with open(vss_path, "rb") as f:
                            f.read(1)
                        self.logger.info(f"File '{original_path}' recovered via VSS snapshot: '{vss_path}'")
                        return FileInspectionResult(
                            state=FileLockState.VSS_READABLE,
                            effective_path=vss_path,
                            size_bytes=vss_st.st_size,
                            modified_time=vss_st.st_mtime,
                            is_vss_used=True
                        )
                    except Exception as vss_err:
                        self.logger.debug(f"VSS read failed for '{vss_path}': {vss_err}")

            return FileInspectionResult(
                state=FileLockState.LOCKED,
                effective_path=original_path,
                size_bytes=0,
                modified_time=0.0,
                error_message=str(e),
                is_vss_used=False
            )
        except OSError as e:
            return FileInspectionResult(
                state=FileLockState.ACCESS_DENIED,
                effective_path=original_path,
                size_bytes=0,
                modified_time=0.0,
                error_message=str(e),
                is_vss_used=False
            )

    def verify_consistency_after_read(
        self,
        file_path: str,
        expected_size: int,
        expected_mtime: float
    ) -> bool:
        """
        Verify file was not altered while reading (Phase 12: CHANGED_DURING_BACKUP protection).
        """
        try:
            st = os.stat(file_path)
            if st.st_size != expected_size or abs(st.st_mtime - expected_mtime) > 0.001:
                self.logger.warning(
                    f"File modified during backup: '{file_path}' "
                    f"(size: {expected_size}->{st.st_size}, mtime: {expected_mtime}->{st.st_mtime})"
                )
                return False
            return True
        except OSError:
            return False

    def verify_consistency(
        self,
        file_path: str,
        initial_stat: FileInspectionResult
    ) -> Tuple[bool, Optional[str]]:
        """Verify file was not altered while reading, returning tuple (is_consistent, reason)."""
        try:
            st = os.stat(file_path)
            if st.st_size != initial_stat.size_bytes:
                return False, f"Size changed from {initial_stat.size_bytes} to {st.st_size}"
            if abs(st.st_mtime - initial_stat.modified_time) > 0.001:
                return False, f"Mtime changed from {initial_stat.modified_time} to {st.st_mtime}"
            return True, None
        except OSError as e:
            return False, str(e)
