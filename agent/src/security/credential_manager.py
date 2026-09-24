"""Agent Security Credential Manager for RetroVault V7."""

import os
import json
import uuid
import datetime
from typing import Optional, Dict, Any
try:
    from agent.src.utils.windows import get_programdata_path
    from agent.src.utils.filesystem import atomic_write_json, ensure_directory
except ImportError:
    from utils.windows import get_programdata_path
    from utils.filesystem import atomic_write_json, ensure_directory


def get_default_credential_path() -> str:
    """Return standard credentials.json path under ProgramData."""
    program_data = get_programdata_path()
    return os.path.join(program_data, "RetroVault", "agent", "credentials.json")


class AgentCredentialManager:
    """Manages persistent cryptographic token credentials and rotation for the Windows Agent."""

    def __init__(self, credential_path: Optional[str] = None):
        self.credential_path = credential_path or get_default_credential_path()
        self.active_token: Optional[str] = None
        self.pending_token: Optional[str] = None
        self.last_rotated_at: Optional[str] = None
        self.credential_id: Optional[int] = None
        self._load()

    def _load(self):
        """Load credentials from disk if present."""
        if os.path.exists(self.credential_path):
            try:
                with open(self.credential_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.active_token = data.get("active_token")
                self.pending_token = data.get("pending_token")
                self.last_rotated_at = data.get("last_rotated_at")
                self.credential_id = data.get("credential_id")
            except Exception:
                pass

    def save(self):
        """Persist credentials atomically."""
        ensure_directory(os.path.dirname(self.credential_path))
        data = {
            "active_token": self.active_token,
            "pending_token": self.pending_token,
            "last_rotated_at": self.last_rotated_at,
            "credential_id": self.credential_id
        }
        atomic_write_json(self.credential_path, json.dumps(data, indent=2))

    def set_pending_token(self, new_token: str, credential_id: int):
        """Stage a newly received token from rotation response."""
        self.pending_token = new_token
        self.credential_id = credential_id
        self.save()

    def confirm_pending_token(self):
        """Promote pending token to active and clear pending."""
        if self.pending_token:
            self.active_token = self.pending_token
            self.pending_token = None
            self.last_rotated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            self.save()

    def get_auth_token(self) -> Optional[str]:
        """Return the current active authentication token."""
        return self.active_token or self.pending_token
