"""RetroVault Platform Adapter Package.

Provides clean OS-specific abstractions:
- WindowsPlatformAdapter: Win32 native scanning, VSS, USN Journal, Win32 locked file I/O
- LinuxPlatformAdapter: POSIX streaming, capability-based snapshot, fcntl locks, special device filtering
"""

import sys
from typing import Optional
from agent.src.platform.base import PlatformAdapter, FileReadInspection
from agent.src.platform.windows import WindowsPlatformAdapter
from agent.src.platform.linux import LinuxPlatformAdapter

_CURRENT_ADAPTER: Optional[PlatformAdapter] = None


def get_platform_adapter(force_os: Optional[str] = None) -> PlatformAdapter:
    """Return the active PlatformAdapter for the current OS (or forced for simulation/testing)."""
    global _CURRENT_ADAPTER
    if force_os:
        if force_os.lower().startswith("win"):
            return WindowsPlatformAdapter()
        return LinuxPlatformAdapter()

    if _CURRENT_ADAPTER is None:
        if sys.platform.startswith("win"):
            _CURRENT_ADAPTER = WindowsPlatformAdapter()
        else:
            _CURRENT_ADAPTER = LinuxPlatformAdapter()
    return _CURRENT_ADAPTER


def set_platform_adapter(adapter: Optional[PlatformAdapter]) -> None:
    """Explicitly configure the active platform adapter (for testing)."""
    global _CURRENT_ADAPTER
    _CURRENT_ADAPTER = adapter


__all__ = [
    "PlatformAdapter",
    "FileReadInspection",
    "WindowsPlatformAdapter",
    "LinuxPlatformAdapter",
    "get_platform_adapter",
    "set_platform_adapter"
]
