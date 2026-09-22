"""Policy Resolver module for converting universal server policies to local machine targets."""

import os
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from agent.src.user_discovery import UserProfile, discover_user_profiles
from agent.src.path_resolver import resolve_universal_path
from agent.src.utils.filesystem import canonicalize_path, is_path_accessible
from agent.src.utils.validation import validate_path_safety
from agent.src.logger import get_logger


@dataclass
class ResolvedPolicy:
    """Represents the local resolution of a backup policy."""
    policy_id: Optional[int] = None
    policy_name: str = "Default Policy"
    valid_paths: List[str] = field(default_factory=list)
    missing_paths: List[str] = field(default_factory=list)
    excluded_paths: List[str] = field(default_factory=list)
    invalid_paths: List[str] = field(default_factory=list)
    rpo_target_seconds: int = 120
    compression_enabled: bool = True
    encryption_enabled: bool = True
    cpu_limit_percent: int = 10
    network_limit_mbps: int = 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "policy_name": self.policy_name,
            "valid_paths_count": len(self.valid_paths),
            "valid_paths": self.valid_paths,
            "missing_paths": self.missing_paths,
            "excluded_paths": self.excluded_paths,
            "invalid_paths": self.invalid_paths,
            "rpo_target_seconds": self.rpo_target_seconds,
            "compression_enabled": self.compression_enabled,
            "encryption_enabled": self.encryption_enabled,
            "cpu_limit_percent": self.cpu_limit_percent,
            "network_limit_mbps": self.network_limit_mbps,
        }


class PolicyResolver:
    """Transforms server-provided abstract policies into validated local machine targets."""

    def __init__(self, profiles: Optional[List[UserProfile]] = None):
        self.profiles = profiles
        self.logger = get_logger()

    def resolve_policy(self, raw_policy: Dict[str, Any]) -> ResolvedPolicy:
        """Parse, expand, validate, and deduplicate a backup policy."""
        # Refresh user profiles if not provided
        profiles = self.profiles if self.profiles is not None else discover_user_profiles()

        policy_id = raw_policy.get("id")
        policy_name = raw_policy.get("name", "Standard Policy")
        rpo_target = raw_policy.get("rpo_target_seconds", 120)
        compression = raw_policy.get("compression_enabled", True)
        encryption = raw_policy.get("encryption_enabled", True)
        cpu_limit = raw_policy.get("cpu_limit_percent", 10)
        network_limit = raw_policy.get("network_limit_mbps", 100)

        # Handle both list of path dicts format and list of string include/exclude paths
        raw_includes: List[str] = []
        raw_excludes: List[str] = []

        if "paths" in raw_policy and isinstance(raw_policy["paths"], list):
            for p in raw_policy["paths"]:
                if isinstance(p, dict):
                    val = p.get("path_value")
                    if val:
                        if p.get("is_excluded", False):
                            raw_excludes.append(val)
                        else:
                            raw_includes.append(val)
                elif isinstance(p, str):
                    raw_includes.append(p)
        else:
            raw_includes = raw_policy.get("include_paths", [])
            raw_excludes = raw_policy.get("exclude_paths", [])

        # 1. Resolve and expand all exclusions
        resolved_exclusions: Set[str] = set()
        for raw_exc in raw_excludes:
            for exp in resolve_universal_path(raw_exc, profiles):
                resolved_exclusions.add(exp.lower())

        # 2. Resolve and expand include paths across all discovered users
        candidate_paths: List[str] = []
        for raw_inc in raw_includes:
            for exp in resolve_universal_path(raw_inc, profiles):
                candidate_paths.append(exp)

        # 3. Deduplicate candidate paths preserving order
        unique_candidates: List[str] = []
        seen_candidates: Set[str] = set()
        for p in candidate_paths:
            p_clean = canonicalize_path(p)
            p_lower = p_clean.lower()
            if p_lower not in seen_candidates:
                seen_candidates.add(p_lower)
                unique_candidates.append(p_clean)

        # 4. Filter, validate, and check accessibility
        valid_paths: List[str] = []
        missing_paths: List[str] = []
        invalid_paths: List[str] = []
        excluded_found: List[str] = []

        for path in unique_candidates:
            path_lower = path.lower()

            # Check if explicitly excluded or inside an excluded directory
            is_excluded = False
            for exc in resolved_exclusions:
                if path_lower == exc or path_lower.startswith(exc.rstrip(os.sep) + os.sep):
                    is_excluded = True
                    break
            if is_excluded:
                excluded_found.append(path)
                continue

            # Validate path safety against directory traversal or root system files
            is_safe, error_msg = validate_path_safety(path)
            if not is_safe:
                self.logger.warning(f"Rejecting unsafe path '{path}': {error_msg}")
                invalid_paths.append(path)
                continue

            # Check filesystem existence
            if not os.path.exists(path):
                self.logger.warning(f"Configured backup path does not exist: '{path}' (Reporting as missing)")
                missing_paths.append(path)
                continue

            # Verify accessibility
            if not is_path_accessible(path):
                self.logger.warning(f"Path exists but is not accessible due to permissions: '{path}'")
                missing_paths.append(path)
                continue

            valid_paths.append(path)

        # 5. Remove redundant sub-directories
        # (e.g. if C:\Users\Arun\Documents is included, don't separately keep C:\Users\Arun\Documents\sub)
        final_valid_paths = self._prune_nested_subpaths(valid_paths)

        return ResolvedPolicy(
            policy_id=policy_id,
            policy_name=policy_name,
            valid_paths=final_valid_paths,
            missing_paths=missing_paths,
            excluded_paths=list(resolved_exclusions),
            invalid_paths=invalid_paths,
            rpo_target_seconds=rpo_target,
            compression_enabled=compression,
            encryption_enabled=encryption,
            cpu_limit_percent=cpu_limit,
            network_limit_mbps=network_limit,
        )

    def _prune_nested_subpaths(self, paths: List[str]) -> List[str]:
        """Eliminate subpaths that are already enclosed by another included parent directory."""
        if not paths:
            return []

        # Sort by path length so parents come before children
        sorted_paths = sorted(paths, key=lambda x: (len(x), x))
        retained: List[str] = []

        for p in sorted_paths:
            p_norm = os.path.normcase(p).rstrip(os.sep) + os.sep
            is_child_of_existing = False
            for parent in retained:
                parent_norm = os.path.normcase(parent).rstrip(os.sep) + os.sep
                if p_norm.startswith(parent_norm) and p_norm != parent_norm:
                    is_child_of_existing = True
                    break
            if not is_child_of_existing:
                retained.append(p)

        return retained
