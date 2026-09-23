"""Conflict Resolution Policies for RetroVault Agent Restore."""

import os
from typing import Tuple, Optional


class RestoreConflictError(Exception):
    """Raised when conflict policy is FAIL and destination already exists."""
    pass


class ConflictResolver:
    """Evaluates and resolves target destination paths based on configured policy."""

    @staticmethod
    def resolve_target(destination_path: str, policy: str) -> Tuple[str, str]:
        """
        Determines the action and final target path.
        Returns: (action, resolved_path)
        action is one of: 'WRITE', 'SKIP'
        """
        pol = policy.upper() if policy else "OVERWRITE"

        if not os.path.exists(destination_path):
            return "WRITE", destination_path

        if pol == "SKIP":
            return "SKIP", destination_path
        elif pol == "FAIL":
            raise RestoreConflictError(f"File already exists at destination: {destination_path}")
        elif pol == "OVERWRITE":
            return "WRITE", destination_path
        elif pol == "RENAME":
            renamed = ConflictResolver.generate_renamed_path(destination_path)
            return "WRITE", renamed
        else:
            raise ValueError(f"Unknown conflict policy: {policy}")

    @staticmethod
    def generate_renamed_path(path: str) -> str:
        """Generate a non-colliding alternative path: file (Restored).ext"""
        folder, filename = os.path.split(path)
        base, ext = os.path.splitext(filename)
        candidate = os.path.join(folder, f"{base} (Restored){ext}")
        counter = 1
        while os.path.exists(candidate):
            candidate = os.path.join(folder, f"{base} (Restored {counter}){ext}")
            counter += 1
        return candidate
