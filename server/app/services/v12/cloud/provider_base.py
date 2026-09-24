"""Provider-neutral cloud object storage interface for RetroVault V12."""

import datetime
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union, BinaryIO


class CloudProviderError(Exception):
    """Base exception for cloud object storage failures."""
    def __init__(self, message: str, provider: str = "cloud", status_code: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.status_code = status_code

    def __str__(self) -> str:
        # Never leak secrets in string representation
        return f"[{self.provider}] {self.message}"


class CloudAuthenticationError(CloudProviderError):
    """Authentication or signature failure with cloud provider."""
    pass


class CloudBucketNotFoundError(CloudProviderError):
    """The requested bucket does not exist or cannot be accessed."""
    pass


class CloudObjectNotFoundError(CloudProviderError):
    """The requested object key was not found."""
    pass


class CloudChecksumMismatchError(CloudProviderError):
    """Checksum or integrity verification failed between local and remote object."""
    pass


class CloudTimeoutError(CloudProviderError):
    """Network connection or operation timeout."""
    pass


class CloudPermissionError(CloudProviderError):
    """Access denied / forbidden on the cloud bucket or object."""
    pass


class CloudObjectLockError(CloudProviderError):
    """WORM or Object Lock retention error or violation."""
    pass


class CloudRateLimitError(CloudProviderError):
    """HTTP 429 Too Many Requests or provider throttling."""
    pass


class CloudNetworkError(CloudProviderError):
    """Transient network or transport level error."""
    pass


class CloudProviderBase(ABC):
    """
    Abstract interface for object storage providers.
    Neutral across AWS S3, MinIO, Wasabi, Google Cloud Storage, Azure Blob, and in-memory mock.
    """

    @abstractmethod
    def test_connection(self) -> Dict[str, Any]:
        """
        Verify connection and bucket reachability.
        Returns a dict summarizing status, latency_ms, bucket, and capabilities.
        """
        pass

    @abstractmethod
    def upload_object(
        self,
        key: str,
        data: Union[bytes, BinaryIO],
        metadata: Optional[Dict[str, str]] = None,
        expected_sha256: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload an object to the remote bucket.
        Returns dict containing at minimum: key, size, sha256, etag.
        Raises CloudChecksumMismatchError if expected_sha256 does not match.
        """
        pass

    @abstractmethod
    def download_object(self, key: str) -> bytes:
        """
        Download object bytes by key.
        Raises CloudObjectNotFoundError if not found.
        """
        pass

    @abstractmethod
    def head_object(self, key: str) -> Dict[str, Any]:
        """
        Retrieve object metadata without downloading full body.
        Returns dict containing: key, size, etag, sha256 (if known), modified_at, metadata.
        Raises CloudObjectNotFoundError if not found.
        """
        pass

    @abstractmethod
    def delete_object(self, key: str) -> bool:
        """
        Delete an object by key.
        Returns True if deleted or object did not exist.
        """
        pass

    @abstractmethod
    def object_exists(self, key: str) -> bool:
        """
        Check if an object exists remotely.
        """
        pass

    @abstractmethod
    def list_objects(self, prefix: str = "", limit: int = 1000) -> List[Dict[str, Any]]:
        """
        List objects under prefix.
        Returns list of dicts with: key, size, etag, modified_at.
        """
        pass

    @abstractmethod
    def supports_object_lock(self) -> bool:
        """
        Whether the current provider/bucket configuration supports Object Lock (WORM).
        """
        pass

    @abstractmethod
    def set_object_lock(
        self,
        key: str,
        mode: str,  # GOVERNANCE, COMPLIANCE
        retain_until_date: datetime.datetime
    ) -> bool:
        """
        Apply Object Lock retention to an object.
        """
        pass
