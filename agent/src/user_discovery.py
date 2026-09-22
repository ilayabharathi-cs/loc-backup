"""Dynamic Windows User Profile Discovery Module."""

import os
import sys
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from agent.src.utils.windows import is_windows

try:
    import winreg
except ImportError:
    winreg = None  # type: ignore


# System SIDs that must be excluded from backup
EXCLUDED_SIDS = {
    "S-1-5-18",  # LocalSystem
    "S-1-5-19",  # LocalService
    "S-1-5-20",  # NetworkService
}

# Special directory names that should not be treated as regular user profiles
EXCLUDED_PROFILE_NAMES = {
    "public",
    "default",
    "default user",
    "all users",
    "system",
    "defaultapppool",
}


@dataclass
class UserProfile:
    """Represents an active or provisioned Windows user profile."""
    username: str
    profile_path: str
    sid: Optional[str] = None
    is_active_user: bool = True
    folders: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        # Resolve standard personal user folders dynamically
        standard_folders = ["Desktop", "Documents", "Downloads", "Pictures", "Videos", "Music"]
        for folder in standard_folders:
            folder_path = os.path.join(self.profile_path, folder)
            self.folders[folder] = folder_path


def is_valid_user_directory(dir_name: str, full_path: str) -> bool:
    """Determine if a directory represents an eligible, genuine user profile."""
    name_lower = dir_name.strip().lower()
    if name_lower in EXCLUDED_PROFILE_NAMES:
        return False
    if name_lower.startswith("default.") or name_lower.startswith("$"):
        return False
    if not os.path.isdir(full_path):
        return False
    return True


def discover_profiles_from_registry() -> List[UserProfile]:
    """Query Windows Registry ProfileList for all registered user profiles."""
    profiles: List[UserProfile] = []
    if not is_windows() or winreg is None:
        return profiles

    reg_path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path, 0, winreg.KEY_READ) as key:
            index = 0
            while True:
                try:
                    sid = winreg.EnumKey(key, index)
                    index += 1
                    
                    if sid.upper() in EXCLUDED_SIDS:
                        continue

                    # Read ProfileImagePath for this SID
                    with winreg.OpenKey(key, sid, 0, winreg.KEY_READ) as subkey:
                        profile_image_path, _ = winreg.QueryValueEx(subkey, "ProfileImagePath")
                        expanded_path = os.path.expandvars(profile_image_path)

                        # Determine username from path leaf
                        username = os.path.basename(os.path.normpath(expanded_path))
                        
                        if is_valid_user_directory(username, expanded_path):
                            profiles.append(UserProfile(
                                username=username,
                                profile_path=os.path.normpath(expanded_path),
                                sid=sid
                            ))
                except OSError:
                    # End of subkeys
                    break
    except Exception:
        pass

    return profiles


def discover_profiles_from_filesystem(users_root: Optional[str] = None) -> List[UserProfile]:
    """Scan Users directory dynamically on disk as fallback or supplementary discovery."""
    profiles: List[UserProfile] = []
    
    if not users_root:
        sys_drive = os.environ.get("SYSTEMDRIVE", "C:")
        users_root = os.path.join(sys_drive + "\\", "Users")

    if not os.path.exists(users_root) or not os.path.isdir(users_root):
        # Fallback to home dir parent if Users doesn't exist
        home = os.path.expanduser("~")
        users_root = os.path.dirname(home)

    if os.path.exists(users_root) and os.path.isdir(users_root):
        try:
            for item in os.listdir(users_root):
                full_path = os.path.join(users_root, item)
                if is_valid_user_directory(item, full_path):
                    profiles.append(UserProfile(
                        username=item,
                        profile_path=os.path.normpath(full_path),
                        sid=None
                    ))
        except (PermissionError, OSError):
            pass

    return profiles


def discover_user_profiles(users_root: Optional[str] = None) -> List[UserProfile]:
    """Discover all valid user profiles dynamically on the machine using Registry and Filesystem."""
    # 1. Try Windows Registry first
    discovered = discover_profiles_from_registry()

    # 2. Fall back to or supplement with filesystem scan
    fs_discovered = discover_profiles_from_filesystem(users_root=users_root)

    # Merge avoiding duplicate profile paths
    seen_paths = set()
    final_profiles: List[UserProfile] = []

    for p in discovered:
        norm = os.path.normpath(p.profile_path).lower()
        if norm not in seen_paths:
            seen_paths.add(norm)
            final_profiles.append(p)

    for p in fs_discovered:
        norm = os.path.normpath(p.profile_path).lower()
        if norm not in seen_paths:
            seen_paths.add(norm)
            final_profiles.append(p)

    # 3. Always ensure the currently running user profile is included if valid
    current_home = os.path.expanduser("~")
    current_norm = os.path.normpath(current_home).lower()
    if current_norm not in seen_paths and os.path.exists(current_home):
        current_name = os.path.basename(os.path.normpath(current_home))
        if is_valid_user_directory(current_name, current_home):
            final_profiles.append(UserProfile(
                username=current_name,
                profile_path=os.path.normpath(current_home),
                sid=None
            ))

    return final_profiles
