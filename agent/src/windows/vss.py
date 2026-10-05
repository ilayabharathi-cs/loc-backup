"""Windows Volume Shadow Copy Service (VSS) provider abstraction for RetroVault Local Backup."""

import os
import sys
import ctypes
import subprocess
import re
import atexit
from abc import ABC, abstractmethod
from typing import Optional, Dict, Tuple
from agent.src.logger import get_logger


class VSSProvider(ABC):
    """Abstract base provider for filesystem snapshot consistency."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if snapshot consistency provider is available on current system."""
        pass

    @abstractmethod
    def check_availability(self) -> Tuple[bool, str]:
        """Check availability and return (is_available, diagnostic_reason)."""
        pass

    @abstractmethod
    def create_snapshot(self, volume: str) -> Optional[str]:
        """Create a volume snapshot. Returns snapshot device/mount path, or None if failed."""
        pass

    @abstractmethod
    def get_snapshot_path(self, volume: str, relative_path: str) -> Optional[str]:
        """Translate a volume and relative file path to its snapshot equivalent."""
        pass

    @abstractmethod
    def release_snapshot(self, volume: Optional[str] = None) -> None:
        """Release active snapshot and free resources."""
        pass


class LiveFilesystemProvider(VSSProvider):
    """Direct live filesystem provider with no snapshotting."""

    def is_available(self) -> bool:
        return True

    def check_availability(self) -> Tuple[bool, str]:
        return True, "Live filesystem consistency provider active (no VSS snapshotting requested)"

    def create_snapshot(self, volume: str) -> Optional[str]:
        return None

    def get_snapshot_path(self, volume: str, relative_path: str) -> Optional[str]:
        return os.path.join(volume, relative_path)

    def release_snapshot(self, volume: Optional[str] = None) -> None:
        pass


class WindowsVSSProvider(VSSProvider):
    """
    Windows Volume Shadow Copy Service provider.
    Uses real Windows VSS snapshotting when running elevated on Windows.
    Provides crash-safe cleanup, comprehensive diagnostic logging, and clean fallback.
    Never invents fake snapshot device paths.
    """

    def __init__(self):
        self.logger = get_logger()
        self._active_snapshots: Dict[str, str] = {}  # volume -> snapshot_device_path
        self._active_snapshot_ids: Dict[str, str] = {}  # volume -> shadow_copy_id
        self._registered_cleanup = False
        self._ensure_exit_handler()

    def _ensure_exit_handler(self) -> None:
        if not self._registered_cleanup:
            atexit.register(self._emergency_cleanup)
            self._registered_cleanup = True

    def _emergency_cleanup(self) -> None:
        """Crash safety: release any open shadow copies on process termination."""
        if self._active_snapshots or self._active_snapshot_ids:
            try:
                self.release_snapshot(silent=True)
            except Exception:
                pass

    def check_availability(self) -> Tuple[bool, str]:
        """
        Check if running on Windows with administrative privileges and VSS service available.
        Returns: (is_available, detailed_reason)
        """
        if sys.platform != "win32":
            return False, f"VSS is only supported on Windows (current OS: {sys.platform})"

        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
            if not is_admin:
                return False, "VSS unavailable: Agent process requires Windows Administrator (elevated) privileges"
        except Exception as e:
            return False, f"VSS privilege check failed: {e}"

        # Verify Volume Shadow Copy Service status
        try:
            res = subprocess.run(
                ["sc", "query", "vss"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            if res.returncode != 0:
                return False, f"VSS service query failed (exit code {res.returncode}): {res.stderr.strip()}"
        except Exception as e:
            self.logger.debug(f"VSS service query exception: {e}")

        return True, "VSS available with Windows Administrative privileges"

    def is_available(self) -> bool:
        """Boolean check for VSS availability."""
        avail, _ = self.check_availability()
        return avail

    def create_snapshot(self, volume: str) -> Optional[str]:
        """
        Request creation of a genuine shadow copy for specified volume (e.g. 'C:').
        Uses real Windows vssadmin / WMI tooling if running elevated.
        Falls back cleanly if VSS is unavailable or fails.
        """
        norm_vol = volume.rstrip("\\").upper()
        if not norm_vol.endswith(":"):
            norm_vol = f"{norm_vol}:"

        if norm_vol in self._active_snapshots:
            return self._active_snapshots[norm_vol]

        avail, reason = self.check_availability()
        if not avail:
            self.logger.info(f"VSS snapshot skipped for '{norm_vol}': {reason}. Fallback to live inspection activated.")
            return None

        self.logger.info(f"Initiating Windows VSS shadow copy creation for volume '{norm_vol}'...")
        try:
            # Execute real shadow copy creation
            cmd = ["vssadmin", "create", "shadow", f"/for={norm_vol}\\"]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )

            if result.returncode == 0 and result.stdout:
                match_vol = re.search(r"Shadow Copy Volume Name:\s*([^\r\n]+)", result.stdout, re.IGNORECASE)
                match_id = re.search(r"Shadow Copy ID:\s*([^\r\n]+)", result.stdout, re.IGNORECASE)

                if match_vol:
                    device_path = match_vol.group(1).strip()
                    self._active_snapshots[norm_vol] = device_path
                    if match_id:
                        self._active_snapshot_ids[norm_vol] = match_id.group(1).strip()
                    self.logger.info(
                        f"VSS snapshot created successfully for '{norm_vol}' -> "
                        f"device: {device_path}, id: {self._active_snapshot_ids.get(norm_vol, 'N/A')}"
                    )
                    return device_path

            err_out = result.stderr.strip() or result.stdout.strip()
            self.logger.warning(
                f"VSS snapshot creation failed for volume '{norm_vol}' (exit code {result.returncode}): {err_out}. "
                f"Fallback to live filesystem activated."
            )
            return None
        except subprocess.TimeoutExpired:
            self.logger.warning(f"VSS snapshot creation timed out for volume '{norm_vol}' (>60s). Fallback activated.")
            return None
        except Exception as e:
            self.logger.warning(f"VSS snapshot creation failed for '{norm_vol}': {e}. Fallback to live filesystem activated.")
            return None

    def get_snapshot_path(self, volume: str, relative_path: str) -> Optional[str]:
        """Translate a volume and relative file path to its snapshot equivalent."""
        norm_vol = volume.rstrip("\\").upper()
        if not norm_vol.endswith(":"):
            norm_vol = f"{norm_vol}:"

        snap_device = self._active_snapshots.get(norm_vol)
        if snap_device:
            clean_rel = relative_path.lstrip("\\/")
            snap_clean = snap_device.rstrip("\\/")
            sep = "\\" if "\\" in snap_device or sys.platform == "win32" else os.sep
            mapped_path = f"{snap_clean}{sep}{clean_rel}"
            self.logger.debug(f"Source-to-snapshot mapping: '{volume}\\{relative_path}' -> '{mapped_path}'")
            return mapped_path

        return os.path.join(volume, relative_path)

    def release_snapshot(self, volume: Optional[str] = None, silent: bool = False) -> None:
        """Release active snapshot(s) cleanly and delete shadow copies."""
        targets = [volume] if volume else list(self._active_snapshots.keys())
        for vol in targets:
            snap_id = self._active_snapshot_ids.pop(vol, None)
            snap_dev = self._active_snapshots.pop(vol, None)
            if snap_id and sys.platform == "win32":
                try:
                    subprocess.run(
                        ["vssadmin", "delete", "shadows", f"/shadow={snap_id}", "/quiet"],
                        capture_output=True,
                        timeout=30,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    if not silent:
                        self.logger.info(f"Snapshot released: volume '{vol}', shadow ID '{snap_id}'")
                except Exception as del_err:
                    if not silent:
                        self.logger.warning(f"VSS shadow deletion error for '{vol}' ({snap_id}): {del_err}")
            elif snap_dev and not silent:
                self.logger.info(f"Snapshot released from memory for volume '{vol}' ({snap_dev})")


def get_vss_provider(consistency_mode: str = "VSS_WHEN_REQUIRED") -> VSSProvider:
    """Factory creating appropriate VSS provider based on configuration."""
    mode = (consistency_mode or "LIVE").upper()
    if mode == "LIVE":
        return LiveFilesystemProvider()
    return WindowsVSSProvider()
