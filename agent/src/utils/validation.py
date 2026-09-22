"""Validation utility functions for path safety, URL checking, and system directory protection."""

import os
import re
from typing import Tuple, Optional
from urllib.parse import urlparse


def is_valid_server_url(url: str) -> bool:
    """Validate that the given string is a valid HTTP/HTTPS URL."""
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url.strip())
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def get_system_critical_directories() -> set[str]:
    """Dynamically determine system-critical directories to protect against unintended backup."""
    critical = set()
    
    # Dynamic SystemRoot (usually C:\Windows, but could be on any drive or custom install)
    system_root = os.environ.get("SYSTEMROOT") or os.environ.get("WINDIR")
    if system_root:
        critical.add(os.path.normpath(system_root).lower())

    # Dynamic SystemDrive (usually C:, but could be D:, E:, etc.)
    system_drive = os.environ.get("SYSTEMDRIVE")
    if system_drive:
        critical.add(os.path.normpath(os.path.join(system_drive + "\\", "Boot")).lower())
        critical.add(os.path.normpath(os.path.join(system_drive + "\\", "System Volume Information")).lower())
        critical.add(os.path.normpath(os.path.join(system_drive + "\\", "$Recycle.Bin")).lower())
        critical.add(os.path.normpath(os.path.join(system_drive + "\\", "pagefile.sys")).lower())
        critical.add(os.path.normpath(os.path.join(system_drive + "\\", "hiberfil.sys")).lower())
        critical.add(os.path.normpath(os.path.join(system_drive + "\\", "swapfile.sys")).lower())

    return critical


def validate_path_safety(path: str, allow_system_dirs: bool = False) -> Tuple[bool, Optional[str]]:
    """Verify that a path is safe for backup, preventing traversal loops or unsafe roots."""
    if not path or not isinstance(path, str):
        return False, "Path is empty or invalid"

    trimmed = path.strip()
    if not trimmed:
        return False, "Path cannot be blank"

    # Check for raw traversal attempts
    normalized = os.path.normpath(trimmed)
    if ".." in normalized.split(os.sep):
        return False, f"Directory traversal detected in path: {path}"

    # Protect against backing up entire system-critical roots
    if not allow_system_dirs:
        critical_dirs = get_system_critical_directories()
        norm_lower = normalized.lower()
        
        # Exact match or parent directory matches
        for cdir in critical_dirs:
            if norm_lower == cdir:
                return False, f"Path is a protected system directory: {path}"

    return True, None
