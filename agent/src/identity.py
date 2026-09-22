"""Persistent Device Identity Manager for RetroVault Backup Agent."""

import os
import json
import uuid
import datetime
from typing import Optional, Dict, Any
from agent.src.utils.windows import get_programdata_path
from agent.src.utils.filesystem import atomic_write_json, ensure_directory


def get_default_identity_path() -> str:
    """Return standard identity.json path under ProgramData."""
    program_data = get_programdata_path()
    return os.path.join(program_data, "RetroVault", "agent", "identity.json")


class DeviceIdentity:
    """Manages persistent cryptographic device identity across restarts."""

    def __init__(self, identity_file_path: Optional[str] = None):
        self.identity_file_path = identity_file_path or get_default_identity_path()
        self.device_id: str = ""
        self.client_id: Optional[str] = None
        self.created_at: Optional[str] = None
        self.registered_at: Optional[str] = None

        self._load_or_generate()

    def _load_or_generate(self) -> None:
        """Load existing identity from disk or generate a new cryptographically secure UUID."""
        if os.path.exists(self.identity_file_path):
            try:
                with open(self.identity_file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                loaded_device_id = data.get("device_id")
                if loaded_device_id and isinstance(loaded_device_id, str) and len(loaded_device_id.strip()) > 10:
                    self.device_id = loaded_device_id.strip()
                    self.client_id = data.get("client_id")
                    self.created_at = data.get("created_at")
                    self.registered_at = data.get("registered_at")
                    return
            except Exception:
                # Corrupt file; will generate and overwrite safely
                pass

        # Generate a new persistent UUIDv4
        self.device_id = f"urn:uuid:{uuid.uuid4()}"
        self.created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.save()

    def set_registration(self, client_id: str) -> None:
        """Save server-assigned client_id and registration timestamp."""
        self.client_id = client_id
        self.registered_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.save()

    def save(self) -> None:
        """Persist current identity state to disk atomically."""
        ensure_directory(os.path.dirname(self.identity_file_path))
        data = {
            "device_id": self.device_id,
            "client_id": self.client_id,
            "created_at": self.created_at,
            "registered_at": self.registered_at,
        }
        atomic_write_json(self.identity_file_path, json.dumps(data, indent=2))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "client_id": self.client_id,
            "created_at": self.created_at,
            "registered_at": self.registered_at,
            "identity_file_path": self.identity_file_path
        }
