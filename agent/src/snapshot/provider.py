"""RetroVault Snapshot Provider Interface and Implementations.

Supports:
- VssSnapshotProvider (Windows)
- LinuxSnapshotProvider (Linux, capability-based with LIVE_FILE_FALLBACK)
- LiveFallbackSnapshotProvider (Universal fallback)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any
import os
import sys
import uuid
import shutil
import subprocess

from agent.src.logger import get_logger


@dataclass
class SnapshotContext:
    """Represents an active snapshot session context."""
    snapshot_id: str
    original_path: str
    snapshot_path: str
    provider_name: str
    is_live_fallback: bool = False
    details: Optional[Dict[str, Any]] = None


class SnapshotProvider(ABC):
    """Abstract base class for platform point-in-time snapshot providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if this snapshot mechanism is supported and available in the current environment."""
        pass

    @abstractmethod
    def create_snapshot(self, path: str) -> SnapshotContext:
        """Create a point-in-time snapshot context for the given path.
        
        Must return a valid SnapshotContext. If hardware/OS snapshot is unsupported,
        must return a SnapshotContext with is_live_fallback=True and snapshot_path=path.
        Never generates fake snapshot paths.
        """
        pass

    @abstractmethod
    def release_snapshot(self, context: SnapshotContext) -> None:
        """Clean up and release resources associated with the snapshot session."""
        pass


class LiveFallbackSnapshotProvider(SnapshotProvider):
    """Universal fallback provider that safely accesses live files with consistency checks."""

    @property
    def name(self) -> str:
        return "LIVE_FILE_FALLBACK"

    def is_available(self) -> bool:
        return True

    def create_snapshot(self, path: str) -> SnapshotContext:
        canon = os.path.abspath(os.path.normpath(path))
        return SnapshotContext(
            snapshot_id=f"live-{uuid.uuid4().hex[:12]}",
            original_path=canon,
            snapshot_path=canon,
            provider_name=self.name,
            is_live_fallback=True,
            details={"mode": "live_filesystem", "consistency": "file_level_atomic_check"}
        )

    def release_snapshot(self, context: SnapshotContext) -> None:
        # No system snapshot resources to release for live fallback
        pass


class VssSnapshotProvider(SnapshotProvider):
    """Windows Volume Shadow Copy Service (VSS) provider."""

    def __init__(self, mode: str = "VSS_WHEN_REQUIRED"):
        self.mode = mode
        self.logger = get_logger()
        self._live_fallback = LiveFallbackSnapshotProvider()

    @property
    def name(self) -> str:
        return "WINDOWS_VSS"

    def is_available(self) -> bool:
        if sys.platform != "win32":
            return False
        try:
            from agent.src.windows.vss import get_vss_provider
            vss = get_vss_provider(self.mode)
            return vss.is_available()
        except Exception:
            return False

    def create_snapshot(self, path: str) -> SnapshotContext:
        canon = os.path.abspath(os.path.normpath(path))
        if sys.platform != "win32":
            return self._live_fallback.create_snapshot(path)

        try:
            from agent.src.windows.vss import get_vss_provider
            vss = get_vss_provider(self.mode)
            if vss.is_available():
                drive = os.path.splitdrive(canon)[0] or "C:"
                session = vss.create_snapshot_session([drive])
                if session and session.session_id:
                    shadow_path = vss.resolve_shadow_path(canon, session)
                    if shadow_path and os.path.exists(shadow_path):
                        return SnapshotContext(
                            snapshot_id=session.session_id,
                            original_path=canon,
                            snapshot_path=shadow_path,
                            provider_name=self.name,
                            is_live_fallback=False,
                            details={"volume": drive, "shadow_device": shadow_path}
                        )
                    # Release failed session
                    vss.release_snapshot_session(session.session_id)
        except Exception as e:
            self.logger.warning(f"VSS snapshot failed ({e}); falling back cleanly to LIVE_FILE_FALLBACK.")

        # Clean fallback to live filesystem
        return self._live_fallback.create_snapshot(path)

    def release_snapshot(self, context: SnapshotContext) -> None:
        if context.is_live_fallback or sys.platform != "win32":
            return
        try:
            from agent.src.windows.vss import get_vss_provider
            vss = get_vss_provider(self.mode)
            vss.release_snapshot_session(context.snapshot_id)
        except Exception as e:
            self.logger.warning(f"Error releasing VSS snapshot session {context.snapshot_id}: {e}")


class LinuxSnapshotProvider(SnapshotProvider):
    """Linux capability-based snapshot provider.
    
    Inspects volume capabilities (LVM, Btrfs, ZFS). If no suitable snapshot
    mechanism is configured, cleanly falls back to LIVE_FILE_FALLBACK.
    Never generates fake snapshot paths.
    """

    def __init__(self):
        self.logger = get_logger()
        self._live_fallback = LiveFallbackSnapshotProvider()

    @property
    def name(self) -> str:
        return "LINUX_SNAPSHOT"

    def is_available(self) -> bool:
        if sys.platform.startswith("win"):
            return False
        # Check if any Linux snapshot capability tool exists
        for tool in ["btrfs", "lvs", "zfs"]:
            if shutil.which(tool):
                return True
        return False

    def check_path_capability(self, path: str) -> str:
        """Detect snapshot capability for a specific mount or path."""
        canon = os.path.abspath(os.path.normpath(path))
        if sys.platform.startswith("win"):
            return "UNSUPPORTED"

        # Check Btrfs subvolume
        if shutil.which("btrfs"):
            try:
                res = subprocess.run(
                    ["btrfs", "subvolume", "show", canon],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                if res.returncode == 0:
                    return "BTRFS"
            except Exception:
                pass

        # Check ZFS dataset
        if shutil.which("zfs"):
            try:
                res = subprocess.run(
                    ["zfs", "list", canon],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                if res.returncode == 0:
                    return "ZFS"
            except Exception:
                pass

        # Default standard Linux filesystems without explicit snapshot layer
        return "LIVE_FILE_FALLBACK"

    def create_snapshot(self, path: str) -> SnapshotContext:
        canon = os.path.abspath(os.path.normpath(path))
        capability = self.check_path_capability(canon)

        if capability == "BTRFS":
            # Attempt Btrfs read-only snapshot
            snapshot_dir = os.path.join(os.path.dirname(canon), f".rv_snap_{uuid.uuid4().hex[:8]}")
            try:
                res = subprocess.run(
                    ["btrfs", "subvolume", "snapshot", "-r", canon, snapshot_dir],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if res.returncode == 0 and os.path.exists(snapshot_dir):
                    self.logger.info(f"Created Btrfs point-in-time snapshot at: {snapshot_dir}")
                    return SnapshotContext(
                        snapshot_id=f"btrfs-{uuid.uuid4().hex[:12]}",
                        original_path=canon,
                        snapshot_path=snapshot_dir,
                        provider_name="BTRFS_SNAPSHOT",
                        is_live_fallback=False,
                        details={"type": "btrfs", "mount": snapshot_dir}
                    )
            except Exception as e:
                self.logger.warning(f"Btrfs snapshot attempt failed ({e}); falling back to live filesystem.")

        # Capability not present or unsupported: Clean documented live filesystem fallback
        self.logger.debug(
            f"No hardware/volume snapshot layer on '{canon}' ({capability}). "
            "Engaging documented LIVE_FILE_FALLBACK."
        )
        return self._live_fallback.create_snapshot(path)

    def release_snapshot(self, context: SnapshotContext) -> None:
        if context.is_live_fallback:
            return

        if context.provider_name == "BTRFS_SNAPSHOT" and os.path.exists(context.snapshot_path):
            try:
                subprocess.run(
                    ["btrfs", "subvolume", "delete", context.snapshot_path],
                    capture_output=True,
                    timeout=10
                )
                self.logger.debug(f"Released Btrfs snapshot: {context.snapshot_path}")
            except Exception as e:
                self.logger.warning(f"Error deleting Btrfs snapshot {context.snapshot_path}: {e}")


def get_snapshot_provider(force_os: Optional[str] = None, mode: str = "VSS_WHEN_REQUIRED") -> SnapshotProvider:
    """Return the appropriate snapshot provider based on current OS."""
    os_name = (force_os or sys.platform).lower()
    if os_name.startswith("win"):
        return VssSnapshotProvider(mode=mode)
    elif "linux" in os_name or not os_name.startswith("win"):
        return LinuxSnapshotProvider()
    return LiveFallbackSnapshotProvider()
