"""Windows Platform Adapter for RetroVault Hybrid Windows Backup Agent.

Wraps existing native C/C++ acceleration (scanner.cpp, file_io.cpp, vss_provider.cpp, usn_provider.cpp)
with full transparent Python fallbacks.
"""

import os
import sys
from typing import List, Dict, Any, Optional

from agent.src.platform_adapter.base import PlatformAdapter, FileReadInspection
from agent.src.backup.models import DiscoveredFile
from agent.src.snapshot.provider import SnapshotProvider, VssSnapshotProvider, LiveFallbackSnapshotProvider
from agent.src.logger import get_logger


class WindowsPlatformAdapter(PlatformAdapter):
    """Platform adapter implementing Windows Win32 and NTFS backup operations."""

    def __init__(self):
        self.logger = get_logger()

    @property
    def os_name(self) -> str:
        return "Windows"

    def get_programdata_path(self) -> str:
        """Resolve canonical ProgramData path on Windows."""
        return os.environ.get("PROGRAMDATA") or os.environ.get("ALLUSERSPROFILE") or os.path.join(
            os.environ.get("SYSTEMDRIVE", "C:"), "ProgramData"
        )

    def get_device_identity_path(self) -> str:
        prog_data = self.get_programdata_path()
        return os.path.join(prog_data, "RetroVault", "agent", "identity.json")

    def get_default_config_path(self) -> str:
        prog_data = self.get_programdata_path()
        return os.path.join(prog_data, "RetroVault", "agent", "config.json")

    def get_lock_directory(self) -> str:
        prog_data = self.get_programdata_path()
        return os.path.join(prog_data, "RetroVault", "agent", "locks")

    def get_policy_cache_path(self) -> str:
        prog_data = self.get_programdata_path()
        return os.path.join(prog_data, "RetroVault", "agent", "policy_cache.json")

    def get_system_info(self, device_id: str, agent_version: str) -> Dict[str, Any]:
        from agent.src.system_info import collect_system_info
        return collect_system_info(device_id=device_id, agent_version=agent_version)

    def discover_user_profiles(self) -> List[Any]:
        from agent.src.user_discovery import discover_user_profiles
        return discover_user_profiles()

    def scan_directories(
        self,
        include_paths: List[str],
        exclude_paths: Optional[List[str]] = None
    ) -> List[DiscoveredFile]:
        from agent.src.backup.scanner import FileScanner
        scanner = FileScanner(include_paths=include_paths, exclude_paths=exclude_paths, use_native=True)
        return scanner.scan()

    def get_snapshot_provider(self, mode: str = "VSS_WHEN_REQUIRED") -> SnapshotProvider:
        return VssSnapshotProvider(mode=mode)

    def inspect_file_for_read(self, path: str, relative_path: str = "") -> FileReadInspection:
        from agent.src.windows.locked_files import LockedFileHandler, FileLockState
        handler = LockedFileHandler()
        res = handler.inspect_file(path, relative_path)
        is_acc = res.state not in (FileLockState.ACCESS_DENIED, FileLockState.NOT_FOUND)
        is_lck = (res.state == FileLockState.LOCKED)
        return FileReadInspection(
            effective_path=res.effective_path,
            size_bytes=res.size_bytes,
            modified_time=res.modified_time,
            is_accessible=is_acc,
            is_locked=is_lck,
            is_vss_used=getattr(res, "is_vss_used", False),
            error_message=res.error_message
        )


    def read_file_chunk(self, path: str, offset: int, size: int) -> bytes:
        from agent.native.python.native_bridge import get_native_bridge
        bridge = get_native_bridge()
        if bridge.is_available:
            try:
                return bridge.read_file_chunk(path, offset, size)
            except Exception:
                pass

        # Standard file read fallback
        with open(path, "rb") as f:
            f.seek(offset)
            return f.read(size)

    def acquire_lock(self, lock_file_path: str) -> Any:
        import msvcrt
        os.makedirs(os.path.dirname(lock_file_path), exist_ok=True)
        handle = open(lock_file_path, "wb")
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            return handle
        except (IOError, OSError):
            handle.close()
            raise RuntimeError(f"Lock already held on {lock_file_path}")

    def release_lock(self, lock_handle: Any, lock_file_path: str) -> None:
        import msvcrt
        if lock_handle:
            try:
                msvcrt.locking(lock_handle.fileno(), msvcrt.LK_UNLCK, 1)
            except Exception:
                pass
            try:
                lock_handle.close()
            except Exception:
                pass
        if os.path.exists(lock_file_path):
            try:
                os.remove(lock_file_path)
            except OSError:
                pass
