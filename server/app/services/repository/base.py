"""Base interface for backup object storage repository."""

from abc import ABC, abstractmethod
from typing import BinaryIO, Dict, Any, Tuple, Union


class StorageRepositoryBase(ABC):
    """Abstract base class for immutable backup object repositories."""

    @abstractmethod
    def store_object(
        self,
        client_identifier: str,
        run_id: int,
        object_id: str,
        content: Union[bytes, BinaryIO],
        expected_sha256: str = None
    ) -> Tuple[str, int, str]:
        """
        Store an immutable backup object.
        Returns: (storage_object_relative_path, bytes_written, computed_sha256)
        """
        pass

    @abstractmethod
    def get_object_path(self, client_identifier: str, run_id: int, object_id: str) -> str:
        """Return canonical path to stored object."""
        pass

    @abstractmethod
    def object_exists(self, client_identifier: str, run_id: int, object_id: str) -> bool:
        """Check if an object exists in the repository."""
        pass

    @abstractmethod
    def validate_storage_health(self) -> Dict[str, Any]:
        """Validate repository existence, write access, total capacity, and free space."""
        pass
