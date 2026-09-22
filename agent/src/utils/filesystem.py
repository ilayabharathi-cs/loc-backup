"""Filesystem utility functions for safe, atomic operations and path handling."""

import os
import sys
import shutil
import tempfile
from pathlib import Path
from typing import Optional


def ensure_directory(path: str) -> str:
    """Ensure that a directory exists, creating all parent directories if needed."""
    norm_path = os.path.abspath(os.path.expandvars(os.path.expanduser(path)))
    os.makedirs(norm_path, exist_ok=True)
    return norm_path


def atomic_write_json(file_path: str, content: str) -> None:
    """Safely and atomically write text/JSON to a file using a temp file and replace."""
    abs_path = os.path.abspath(file_path)
    parent_dir = os.path.dirname(abs_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    # Write to a temporary file in the same directory to ensure same filesystem volume
    fd, tmp_path = tempfile.mkstemp(dir=parent_dir, prefix=".tmp_rv_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        # Atomic replace on Windows/POSIX
        os.replace(tmp_path, abs_path)
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise


def canonicalize_path(path: str) -> str:
    """Convert path to normalized, canonical absolute representation."""
    if not path:
        return ""
    expanded = os.path.expandvars(os.path.expanduser(path))
    # Standardize Windows separators
    norm = os.path.normpath(expanded)
    return os.path.abspath(norm)


def is_path_accessible(path: str) -> bool:
    """Check if the path exists and can be read."""
    try:
        if not os.path.exists(path):
            return False
        # Test read access
        if os.path.isdir(path):
            os.listdir(path)
        else:
            with open(path, "rb") as f:
                f.read(1)
        return True
    except (PermissionError, OSError):
        return False
