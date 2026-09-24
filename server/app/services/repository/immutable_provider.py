"""Immutable Repository Capabilities and WORM Enforcement for RetroVault V8.

Provides precise classification between:
- Application-level immutability (soft-locked by software policies)
- Operating system level immutability (Windows read-only attributes, Linux chattr +i)
- Provider-enforced immutability (S3 Object Lock Compliance/Governance mode, ZFS/WORM appliances)
"""

import json
import logging
import os
import platform
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.storage_repository import StorageRepository

logger = logging.getLogger(__name__)


class ImmutabilityProvider:
    """Manages and inspects immutability capabilities of repositories."""

    # Supported immutability levels
    DISABLED = "DISABLED"
    SOFT_IMMUTABLE = "SOFT_IMMUTABLE"  # RetroVault software layer enforces protection
    OS_ENFORCED = "OS_ENFORCED"        # OS filesystem read-only or immutable attribute
    WORM = "WORM"                      # Storage appliance hardware WORM
    OBJECT_LOCK = "OBJECT_LOCK"        # Cloud S3 Compliance/Governance mode

    def __init__(self, db: Session):
        self.db = db

    def get_repository_capabilities(self, repository: StorageRepository) -> Dict[str, Any]:
        """Inspects physical repository configuration and returns factual capabilities."""
        caps: Dict[str, Any] = {
            "repository_id": repository.id,
            "name": repository.name,
            "repository_type": repository.repository_type,
            "immutability_state": repository.immutability_state,
            "supports_object_lock": False,
            "supports_os_immutability": False,
            "supports_soft_immutability": True,
            "enforcement_level": "APPLICATION",
            "compliance_retention_days": 0,
        }

        # Check existing capabilities_json
        if repository.capabilities_json:
            try:
                saved = json.loads(repository.capabilities_json)
                caps.update(saved)
            except Exception:
                pass

        # If S3 compatible
        if repository.repository_type == "S3_COMPATIBLE":
            config = json.loads(repository.configuration or "{}")
            caps["supports_object_lock"] = bool(config.get("object_lock_enabled", False))
            if caps["supports_object_lock"]:
                caps["enforcement_level"] = "PROVIDER"
                caps["immutability_state"] = "OBJECT_LOCK"
        else:
            # Filesystem (Local / Remote)
            # Factual reporting: Local NTFS/EXT4 without hardware WORM is APPLICATION or OS level
            if repository.immutability_state in ["WORM", "OBJECT_LOCK"]:
                # Unless explicitly configured with hardware WORM mount
                caps["enforcement_level"] = "PROVIDER"
            elif repository.immutability_state == "OS_ENFORCED":
                caps["enforcement_level"] = "OPERATING_SYSTEM"
            elif repository.immutability_state == "SOFT_IMMUTABLE":
                caps["enforcement_level"] = "APPLICATION"
            else:
                caps["enforcement_level"] = "NONE"

        return caps

    def set_repository_immutability(
        self,
        repository_id: int,
        immutability_state: str,
        retention_days: int = 30,
        provider_mode: str = "COMPLIANCE"
    ) -> Dict[str, Any]:
        """Configures immutability state on a repository with truthful capability metadata."""
        repo = self.db.query(StorageRepository).filter(StorageRepository.id == repository_id).first()
        if not repo:
            return {"error": f"Repository {repository_id} not found", "success": False}

        valid_states = [self.DISABLED, self.SOFT_IMMUTABLE, self.OS_ENFORCED, self.WORM, self.OBJECT_LOCK]
        if immutability_state not in valid_states:
            return {"error": f"Invalid immutability state: {immutability_state}", "success": False}

        # Truthfulness check: Do not claim OBJECT_LOCK on local filesystem
        if immutability_state == self.OBJECT_LOCK and repo.repository_type == "LOCAL_FILESYSTEM":
            immutability_state = self.SOFT_IMMUTABLE
            logger.info("Downgraded requested OBJECT_LOCK to SOFT_IMMUTABLE for LOCAL_FILESYSTEM repository")

        repo.immutability_state = immutability_state
        repo.protection_mode = "IMMUTABLE" if immutability_state != self.DISABLED else "NORMAL"

        caps = self.get_repository_capabilities(repo)
        caps["compliance_retention_days"] = retention_days
        caps["provider_mode"] = provider_mode
        caps["immutability_state"] = immutability_state
        repo.capabilities_json = json.dumps(caps)

        self.db.commit()
        self.db.refresh(repo)

        return {
            "repository_id": repo.id,
            "immutability_state": repo.immutability_state,
            "protection_mode": repo.protection_mode,
            "capabilities": caps,
            "success": True
        }
