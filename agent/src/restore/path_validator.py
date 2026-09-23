"""Windows Agent Path Safety and Traversal Prevention."""

import os
from typing import Set

WINDOWS_RESERVED_NAMES: Set[str] = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
}


class AgentPathSafetyError(ValueError):
    """Raised when an agent restore path is unsafe or invalid."""
    pass


class AgentPathValidator:
    """Validates destination and relative restore paths on Windows clients."""

    @staticmethod
    def sanitize_relative_path(raw_path: str) -> str:
        if not raw_path or not raw_path.strip():
            raise AgentPathSafetyError("Empty path")

        cleaned = raw_path.strip().replace("/", "\\")
        if cleaned.startswith("\\\\"):
            raise AgentPathSafetyError(f"UNC paths prohibited: {raw_path}")

        drive, tail = os.path.splitdrive(cleaned)
        cleaned = tail.lstrip("\\/")

        norm = os.path.normpath(cleaned)
        parts = norm.split(os.sep)
        for part in parts:
            if part in ("..", "."):
                raise AgentPathSafetyError(f"Path traversal detected in '{raw_path}'")
            base_name = os.path.splitext(part)[0].upper()
            if base_name in WINDOWS_RESERVED_NAMES or part.upper() in WINDOWS_RESERVED_NAMES:
                raise AgentPathSafetyError(f"Windows reserved name '{part}' prohibited in '{raw_path}'")

        if norm.startswith("..") or norm == ".":
            raise AgentPathSafetyError(f"Path traversal detected: {raw_path}")

        return norm

    @classmethod
    def resolve_destination(cls, destination_root: str, relative_path: str) -> str:
        if not destination_root or not destination_root.strip():
            raise AgentPathSafetyError("Destination root cannot be empty")

        clean_rel = cls.sanitize_relative_path(relative_path)
        norm_root = os.path.abspath(os.path.normpath(destination_root))
        dest_candidate = os.path.abspath(os.path.normpath(os.path.join(norm_root, clean_rel)))

        try:
            common = os.path.commonpath([norm_root, dest_candidate])
            if os.path.normcase(common) != os.path.normcase(norm_root):
                raise AgentPathSafetyError(f"Path escapes destination root: {dest_candidate}")
        except ValueError:
            raise AgentPathSafetyError(f"Drive mismatch between root '{norm_root}' and '{dest_candidate}'")

        return dest_candidate
