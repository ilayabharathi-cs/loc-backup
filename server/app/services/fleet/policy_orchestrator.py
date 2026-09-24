"""Enterprise Fleet Policy Orchestration & Versioning for RetroVault V8.

Resolves effective policies using the precedence order:
TEMPORARY_OVERRIDE > CLIENT > GROUP > GLOBAL_DEFAULT
Maintains immutable PolicyVersion records and provides dry-run policy evaluation.
"""

import copy
import datetime
import json
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.backup_policy import BackupPolicy
from app.models.security_v8_models import ClientGroup, PolicyVersion

logger = logging.getLogger(__name__)


class PolicyOrchestrator:
    """Manages policy inheritance hierarchy, versioning, and dry-run simulation."""

    def __init__(self, db: Session):
        self.db = db

    def resolve_effective_policy(self, client_id: int) -> Dict[str, Any]:
        """Resolves the effective policy for a client according to precedence rules."""
        client = self.db.query(Client).filter(Client.id == client_id).first()
        if not client:
            return {"error": f"Client {client_id} not found"}

        # 1. Check Temporary Override (Client level override)
        if getattr(client, "policy_override_id", None):
            override_policy = self.db.query(BackupPolicy).filter(BackupPolicy.id == client.policy_override_id).first()
            if override_policy:
                return self._format_resolved_policy(override_policy, "TEMPORARY_OVERRIDE", client_id)

        # 2. Check Client Group Policy
        if getattr(client, "group_id", None):
            group = self.db.query(ClientGroup).filter(ClientGroup.id == client.group_id).first()
            if group and group.policy_id:
                group_policy = self.db.query(BackupPolicy).filter(BackupPolicy.id == group.policy_id).first()
                if group_policy:
                    return self._format_resolved_policy(group_policy, f"GROUP ({group.name})", client_id, group_id=group.id)

        # 3. Check Global Default Policy
        global_policy = self.db.query(BackupPolicy).filter(BackupPolicy.is_active == True).order_by(BackupPolicy.id.asc()).first()
        if global_policy:
            return self._format_resolved_policy(global_policy, "GLOBAL_DEFAULT", client_id)

        # 4. Fallback default
        return {
            "client_id": client_id,
            "source": "FALLBACK_SYSTEM_DEFAULT",
            "policy_id": None,
            "policy_name": "Fallback Standard",
            "backup_type": "incremental",
            "rpo_target_seconds": 120,
            "compression_enabled": True,
            "encryption_enabled": True,
            "cpu_limit_percent": 10,
            "network_limit_mbps": 100,
            "retention_days": 7,
            "version": 1,
        }

    def _format_resolved_policy(
        self,
        policy: BackupPolicy,
        source: str,
        client_id: int,
        group_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Serializes resolved policy into dictionary."""
        # Find latest policy version
        latest_ver = (
            self.db.query(PolicyVersion)
            .filter(PolicyVersion.policy_id == policy.id)
            .order_by(PolicyVersion.version.desc())
            .first()
        )
        version_num = latest_ver.version if latest_ver else 1

        paths = []
        if hasattr(policy, "paths") and policy.paths:
            for p in policy.paths:
                paths.append({
                    "path_type": p.path_type,
                    "path_value": p.path_value,
                    "is_excluded": p.is_excluded
                })

        return {
            "client_id": client_id,
            "source": source,
            "group_id": group_id,
            "policy_id": policy.id,
            "policy_name": policy.name,
            "backup_type": policy.backup_type,
            "change_detection": policy.change_detection,
            "rpo_target_seconds": policy.rpo_target_seconds,
            "compression_enabled": policy.compression_enabled,
            "encryption_enabled": policy.encryption_enabled,
            "cpu_limit_percent": policy.cpu_limit_percent,
            "network_limit_mbps": policy.network_limit_mbps,
            "retention_days": policy.retention_days,
            "version": version_num,
            "paths": paths
        }

    def create_policy_version(
        self,
        policy_id: int,
        definition: Dict[str, Any],
        change_summary: str,
        created_by: str = "admin"
    ) -> PolicyVersion:
        """Stores an immutable version snapshot of a backup policy."""
        latest = (
            self.db.query(PolicyVersion)
            .filter(PolicyVersion.policy_id == policy_id)
            .order_by(PolicyVersion.version.desc())
            .first()
        )
        next_ver = (latest.version + 1) if latest else 1

        pv = PolicyVersion(
            policy_id=policy_id,
            version=next_ver,
            definition_json=json.dumps(definition),
            change_summary=change_summary,
            created_by=created_by
        )
        self.db.add(pv)
        self.db.commit()
        self.db.refresh(pv)
        return pv

    def simulate_policy_dry_run(self, client_id: int, hypothetical_policy_id: int) -> Dict[str, Any]:
        """Simulates what the effective policy and schedule would look like without applying changes."""
        current = self.resolve_effective_policy(client_id)
        candidate = self.db.query(BackupPolicy).filter(BackupPolicy.id == hypothetical_policy_id).first()
        if not candidate:
            return {"error": f"Policy {hypothetical_policy_id} not found"}

        candidate_resolved = self._format_resolved_policy(candidate, "HYPOTHETICAL_SIMULATION", client_id)

        # Compute differences
        diffs = {}
        for key in ["backup_type", "rpo_target_seconds", "compression_enabled", "encryption_enabled", "cpu_limit_percent", "network_limit_mbps", "retention_days"]:
            cur_val = current.get(key)
            new_val = candidate_resolved.get(key)
            if cur_val != new_val:
                diffs[key] = {"current": cur_val, "proposed": new_val}

        return {
            "client_id": client_id,
            "current_effective_source": current.get("source"),
            "proposed_policy_id": hypothetical_policy_id,
            "proposed_policy_name": candidate.name,
            "diff_count": len(diffs),
            "differences": diffs,
            "simulated_effective_policy": candidate_resolved
        }
