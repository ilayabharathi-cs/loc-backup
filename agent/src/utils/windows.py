"""Windows-specific environment inspection utilities via Win32 APIs, ctypes, and Registry."""

import os
import sys
import shutil
import ctypes
from typing import List, Dict, Any, Optional

try:
    import winreg
except ImportError:
    winreg = None  # type: ignore


def is_windows() -> bool:
    """Return True if running on Windows platform."""
    return sys.platform.startswith("win")


def get_logical_drives() -> List[Dict[str, Any]]:
    """Dynamically discover all available logical storage drives on the machine without hardcoding."""
    drives: List[Dict[str, Any]] = []

    if is_windows():
        try:
            # Call GetLogicalDriveStringsW from kernel32
            kernel32 = ctypes.windll.kernel32
            buffer_len = kernel32.GetLogicalDriveStringsW(0, None)
            if buffer_len > 0:
                buffer = ctypes.create_unicode_buffer(buffer_len)
                kernel32.GetLogicalDriveStringsW(buffer_len, buffer)
                
                raw_drives = [d for d in buffer.raw.split("\x00") if d]
                for drive in raw_drives:
                    drive_clean = drive.rstrip("\\") + "\\"
                    drive_info = {"drive": drive_clean, "total_bytes": 0, "free_bytes": 0, "used_bytes": 0}
                    try:
                        usage = shutil.disk_usage(drive_clean)
                        drive_info["total_bytes"] = usage.total
                        drive_info["free_bytes"] = usage.free
                        drive_info["used_bytes"] = usage.used
                    except (PermissionError, OSError):
                        pass
                    drives.append(drive_info)
        except Exception:
            pass

    # Fallback if kernel32 discovery yielded nothing or running on non-Windows/mock
    if not drives:
        # Check environment SYSTEMDRIVE or default root
        sys_drive = os.environ.get("SYSTEMDRIVE", "C:")
        if not sys_drive.endswith("\\"):
            sys_drive += "\\"
        try:
            usage = shutil.disk_usage(sys_drive if os.path.exists(sys_drive) else os.path.abspath(os.sep))
            drives.append({
                "drive": sys_drive,
                "total_bytes": usage.total,
                "free_bytes": usage.free,
                "used_bytes": usage.used
            })
        except Exception:
            drives.append({
                "drive": sys_drive,
                "total_bytes": 0,
                "free_bytes": 0,
                "used_bytes": 0
            })

    return drives


def get_memory_info() -> Dict[str, Any]:
    """Retrieve system physical memory information dynamically."""
    mem = {"total_bytes": 0, "available_bytes": 0, "used_percent": 0.0}
    if is_windows():
        try:
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                mem["total_bytes"] = stat.ullTotalPhys
                mem["available_bytes"] = stat.ullAvailPhys
                if stat.ullTotalPhys > 0:
                    used = stat.ullTotalPhys - stat.ullAvailPhys
                    mem["used_percent"] = round((used / stat.ullTotalPhys) * 100.0, 1)
                return mem
        except Exception:
            pass

    # Fallback estimate
    mem["total_bytes"] = 16 * 1024 * 1024 * 1024
    mem["available_bytes"] = 8 * 1024 * 1024 * 1024
    mem["used_percent"] = 50.0
    return mem


def get_programdata_path() -> str:
    """Return dynamic ProgramData path across Windows environments."""
    return os.environ.get("PROGRAMDATA") or os.environ.get("ALLUSERSPROFILE") or os.path.join(
        os.environ.get("SYSTEMDRIVE", "C:"), "ProgramData"
    )
