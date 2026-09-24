"""Provider-neutral abstraction for Instant Virtual Recovery."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from app.models.virtual_recovery_v12_models import VirtualRecoverySession


class VirtualRecoveryError(Exception):
    """Base exception for instant virtual recovery errors."""
    def __init__(self, message: str, code: str = "VIRTUAL_RECOVERY_ERROR"):
        super().__init__(message)
        self.message = message
        self.code = code

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


class SessionStateError(VirtualRecoveryError):
    """Raised when an invalid state transition or operation on an incompatible state is attempted."""
    def __init__(self, message: str):
        super().__init__(message, code="INVALID_SESSION_STATE")


class ObjectUnavailableError(VirtualRecoveryError):
    """Raised when a required CAS or Cloud object cannot be located or retrieved."""
    def __init__(self, message: str):
        super().__init__(message, code="OBJECT_UNAVAILABLE")


class IntegrityVerificationError(VirtualRecoveryError):
    """Raised when an object or block fails checksum integrity validation."""
    def __init__(self, message: str):
        super().__init__(message, code="CHECKSUM_VERIFICATION_FAILED")


class MountError(VirtualRecoveryError):
    """Raised when target mounting or virtual link exposure fails."""
    def __init__(self, message: str):
        super().__init__(message, code="MOUNT_FAILED")


class UnmountError(VirtualRecoveryError):
    """Raised when unmounting or cleanup fails."""
    def __init__(self, message: str):
        super().__init__(message, code="UNMOUNT_FAILED")


class VirtualRecoveryProviderBase(ABC):
    """
    Provider-neutral interface for Instant Virtual Recovery.
    Does not tightly couple to iSCSI, VHD, SMB, VMware, or Hyper-V.
    """

    @abstractmethod
    def prepare(self, session: VirtualRecoverySession, manifest: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validates target directories, initializes stub manifest structures, and configures mount points.
        """
        pass

    @abstractmethod
    def mount(self, session: VirtualRecoverySession, target_path: str) -> Dict[str, Any]:
        """
        Exposes the virtual recovery view at target_path for immediate client read access.
        """
        pass

    @abstractmethod
    def read(
        self,
        session: VirtualRecoverySession,
        logical_path: str,
        offset: int = 0,
        length: Optional[int] = None
    ) -> bytes:
        """
        On-demand block/object read.
        Resolves path -> CAS/cloud -> cache -> integrity check -> returns bytes.
        """
        pass

    @abstractmethod
    def prefetch(self, session: VirtualRecoverySession, paths: List[str]) -> Dict[str, Any]:
        """
        Prefetches specified logical files into the bounded recovery cache.
        """
        pass

    @abstractmethod
    def hydrate(self, session: VirtualRecoverySession, max_files: Optional[int] = None) -> Dict[str, Any]:
        """
        Progresses background hydration of remaining unhydrated files.
        """
        pass

    @abstractmethod
    def validate(self, session: VirtualRecoverySession) -> Dict[str, Any]:
        """
        Validates virtual mount health, read responsiveness, and target filesystem integrity.
        """
        pass

    @abstractmethod
    def unmount(self, session: VirtualRecoverySession) -> bool:
        """
        Safely detaches the virtual recovery target, flushing pending state.
        """
        pass

    @abstractmethod
    def cleanup(self, session: VirtualRecoverySession) -> bool:
        """
        Cleans up temporary mount metadata and stub links without deleting restored data.
        """
        pass
