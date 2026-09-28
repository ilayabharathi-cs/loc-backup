"""Path Safety & Traversal Prevention for RetroVault V6 Restore Engine.

Enforces strict path normalization and security checks:
- Rejects path traversal (../, ..\\, ..)
- Rejects UNC path injections
- Rejects Windows reserved device names (CON, PRN, AUX, NUL, COM1-9, LPT1-9)
- Enforces strict destination root containment
"""

import os
import re
from typing import Tuple

WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
}


class PathSafetyError(ValueError):
    """Raised when a path fails security or validity checks."""
    pass


class PathValidator:
    """Validates and canonicalizes source and destination paths during restore."""

    @staticmethod
    def sanitize_relative_path(raw_path: str) -> str:
        """
        Normalize and validate a relative path within a Recovery Point.
        Strips drive letters or leading slashes, ensures no traversal escapes.
        Works identically whether server runs on Linux or Windows.
        """
        if not raw_path or not str(raw_path).strip():
            raise PathSafetyError("Empty or blank path provided")

        cleaned = str(raw_path).strip()

        # Reject UNC paths
        if cleaned.startswith(r"\\") or cleaned.startswith("//"):
            raise PathSafetyError(f"UNC paths are prohibited: {raw_path}")

        # Strip drive letter if present (e.g. C:\Users\... -> Users\...)
        drive, tail = os.path.splitdrive(cleaned)
        cleaned = tail.lstrip(r"\/")

        # Split components across any combination of \ and /
        raw_parts = [p for p in re.split(r"[\\/]+", cleaned) if p]

        safe_parts = []
        for part in raw_parts:
            if part in ("..", "."):
                raise PathSafetyError(f"Path traversal component detected in path: {raw_path}")

            # Check reserved Windows device names (e.g. NUL, CON, AUX, COM1, COM1.txt)
            base_name = os.path.splitext(part)[0].upper()
            if base_name in WINDOWS_RESERVED_NAMES or part.upper() in WINDOWS_RESERVED_NAMES:
                raise PathSafetyError(f"Windows reserved device name prohibited: '{part}' in '{raw_path}'")

            safe_parts.append(part)

        if not safe_parts:
            raise PathSafetyError(f"Path traversal detected: {raw_path}")

        return os.path.join(*safe_parts)

    @classmethod
    def resolve_destination(cls, destination_root: str, relative_path: str) -> str:
        """
        Safely resolve a relative path onto a destination root directory.
        Guarantees the resulting canonical path cannot escape destination_root.
        """
        if not destination_root or not destination_root.strip():
            raise PathSafetyError("Destination root path cannot be empty")

        clean_rel = cls.sanitize_relative_path(relative_path)

        # Canonicalize destination root
        norm_root = os.path.abspath(os.path.normpath(destination_root))

        # Join and canonicalize target
        dest_candidate = os.path.abspath(os.path.normpath(os.path.join(norm_root, clean_rel)))

        # Verify destination candidate is within norm_root
        # Use commonpath or startswith with directory boundary
        try:
            common = os.path.commonpath([norm_root, dest_candidate])
            if os.path.normcase(common) != os.path.normcase(norm_root):
                raise PathSafetyError(
                    f"Destination path escapes designated root: root='{norm_root}', target='{dest_candidate}'"
                )
        except ValueError:
            # Different drives on Windows
            raise PathSafetyError(
                f"Destination path escapes root across different drive letters: '{norm_root}' vs '{dest_candidate}'"
            )

        return dest_candidate
