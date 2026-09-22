"""Universal Path Resolver for Windows environment variables and multi-user profile expansions."""

import os
import re
from typing import List, Optional
from agent.src.user_discovery import UserProfile, discover_user_profiles
from agent.src.utils.filesystem import canonicalize_path


def resolve_system_variables(raw_path: str) -> str:
    """Expand general environment variables (%SYSTEMDRIVE%, %PROGRAMDATA%, %TEMP%, etc.)."""
    if not raw_path:
        return ""
    # Use os.path.expandvars to resolve %VAR%
    expanded = os.path.expandvars(raw_path)
    return expanded


def resolve_path_for_user(raw_path: str, user: UserProfile) -> str:
    """Resolve a path template specifically replacing %USERPROFILE% with the user's profile path."""
    pattern = re.compile(r"%USERPROFILE%", re.IGNORECASE)
    if pattern.search(raw_path):
        resolved = pattern.sub(lambda _: user.profile_path, raw_path)
    else:
        resolved = raw_path

    # Resolve any remaining general system variables
    resolved = resolve_system_variables(resolved)
    return canonicalize_path(resolved)


def resolve_universal_path(raw_path: str, profiles: Optional[List[UserProfile]] = None) -> List[str]:
    """Resolve a logical path template into concrete machine paths across all eligible user profiles."""
    if not raw_path or not raw_path.strip():
        return []

    trimmed = raw_path.strip()
    userprofile_pattern = re.compile(r"%USERPROFILE%", re.IGNORECASE)

    if userprofile_pattern.search(trimmed):
        if profiles is None:
            profiles = discover_user_profiles()

        if not profiles:
            # Fallback to current user's home directory
            home = os.path.expanduser("~")
            fallback_user = UserProfile(username=os.path.basename(home), profile_path=home)
            return [resolve_path_for_user(trimmed, fallback_user)]

        resolved_paths: List[str] = []
        for user in profiles:
            path_for_user = resolve_path_for_user(trimmed, user)
            resolved_paths.append(path_for_user)
        return resolved_paths
    else:
        # Non-user specific path (e.g. %PROGRAMDATA%, %TEMP%, D:\Data)
        expanded = resolve_system_variables(trimmed)
        return [canonicalize_path(expanded)]
