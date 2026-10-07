"""Platform Adapter Base Interface for RetroVault Cross-Platform Agents.

Defines the contract for OS-specific operations:
- File system discovery and special file filtering
- Snapshot providers (VSS vs Linux capabilities)
- Process mutual exclusion (msvcrt vs fcntl)
- Identity & policy cache storage locations
- System telemetry and user profile discovery
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from agent.src.backup.models import DiscoveredFile
from agent.src.snapshot.provider import SnapshotProvider


@dataclass
class FileReadInspection:
    """Status of a file inspection before streaming read."""
    effective_path: str
    size_bytes: int
    modified_time: float
    is_accessible: bool
    is_locked: bool = False
    is_vss_used: bool = False
    error_message: Optional[str] = None



class PlatformAdapter(ABC):
    """Abstract base class for platform-specific agent operations."""

    @property
    @abstractmethod
    def os_name(self) -> str:
        """Operating system name ('Windows' or 'Linux')."""
        pass

    @abstractmethod
    def get_device_identity_path(self) -> str:
        """Canonical path for persistent device identity.json."""
        pass

    @abstractmethod
    def get_default_config_path(self) -> str:
        """Canonical path for default config.json."""
        pass

    @abstractmethod
    def get_lock_directory(self) -> str:
        """Directory for process mutual exclusion locks."""
        pass

    @abstractmethod
    def get_policy_cache_path(self) -> str:
        """Path for local cached policy copy."""
        pass

    @abstractmethod
    def get_system_info(self, device_id: str, agent_version: str) -> Dict[str, Any]:
        """Collect platform-specific system hardware and OS telemetry."""
        pass

    @abstractmethod
    def discover_user_profiles(self) -> List[Any]:
        """Discover user home / profile directories across the machine."""
        pass

    @abstractmethod
    def scan_directories(
        self,
        include_paths: List[str],
        exclude_paths: Optional[List[str]] = None
    ) -> List[DiscoveredFile]:
        """Discover eligible files in include roots respecting platform boundaries and exclusions."""
        pass

    @abstractmethod
    def get_snapshot_provider(self, mode: str = "LIVE") -> SnapshotProvider:
        """Return the platform snapshot provider."""
        pass

    @abstractmethod
    def inspect_file_for_read(self, path: str, relative_path: str = "") -> FileReadInspection:
        """Check if file can be safely streamed, handling locks and permissions."""
        pass

    @abstractmethod
    def read_file_chunk(self, path: str, offset: int, size: int) -> bytes:
        """Read a bounded chunk of bytes from a file safely."""
        pass

    @abstractmethod
    def acquire_lock(self, lock_file_path: str) -> Any:
        """Acquire exclusive file lock. Raises error if already held."""
        pass

    @abstractmethod
    def release_lock(self, lock_handle: Any, lock_file_path: str) -> None:
        """Release the acquired file lock."""
        pass
