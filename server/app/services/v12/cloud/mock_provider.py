"""Deterministic In-Memory / Mock Cloud Provider for RetroVault V12."""

import time
import hashlib
import datetime
from typing import Dict, Any, List, Optional, Union, BinaryIO
from app.services.v12.cloud.provider_base import (
    CloudProviderBase,
    CloudObjectNotFoundError,
    CloudChecksumMismatchError,
    CloudObjectLockError,
    CloudAuthenticationError,
    CloudTimeoutError,
    CloudPermissionError,
    CloudBucketNotFoundError
)


class MockCloudProvider(CloudProviderBase):
    """
    Deterministic in-memory object storage provider.
    Enables offline testing of upload, verification, retry, idempotency, and WORM object lock.
    """

    def __init__(
        self,
        bucket: str = "retrovault-test-bucket",
        supports_lock: bool = True,
        fail_next_upload: Optional[str] = None,  # "timeout", "checksum", "auth", "network"
        fail_next_verify: bool = False
    ):
        self.bucket = bucket
        self.provider_name = "mock"
        self._supports_lock = supports_lock
        self._objects: Dict[str, Dict[str, Any]] = {}  # key -> {data, metadata, sha256, size, etag, lock}
        self.fail_next_upload = fail_next_upload
        self.fail_next_verify = fail_next_verify
        self.upload_count = 0
        self.retry_count = 0

    def test_connection(self) -> Dict[str, Any]:
        if self.bucket == "invalid-bucket-trigger":
            raise CloudBucketNotFoundError(f"Bucket '{self.bucket}' not found", provider="mock", status_code=404)
        return {
            "status": "connected",
            "provider": "mock",
            "bucket": self.bucket,
            "latency_ms": 1.2,
            "object_lock_supported": self._supports_lock
        }

    def upload_object(
        self,
        key: str,
        data: Union[bytes, BinaryIO],
        metadata: Optional[Dict[str, str]] = None,
        expected_sha256: Optional[str] = None
    ) -> Dict[str, Any]:
        self.upload_count += 1

        # Simulate failures if requested
        if self.fail_next_upload == "timeout":
            self.fail_next_upload = None
            raise CloudTimeoutError("Simulated provider connection timeout", provider="mock", status_code=504)
        elif self.fail_next_upload == "auth":
            self.fail_next_upload = None
            raise CloudAuthenticationError("Simulated invalid credentials or signature", provider="mock", status_code=403)
        elif self.fail_next_upload == "network":
            self.fail_next_upload = None
            raise CloudTimeoutError("Simulated transient connection reset", provider="mock", status_code=500)

        # Read data bytes
        if isinstance(data, bytes):
            raw_bytes = data
        else:
            raw_bytes = data.read()

        computed_sha = hashlib.sha256(raw_bytes).hexdigest()

        if self.fail_next_upload == "checksum":
            self.fail_next_upload = None
            # Corrupt computed hash intentionally
            computed_sha = "0000000000000000000000000000000000000000000000000000000000000000"

        if expected_sha256 and expected_sha256.lower() != computed_sha.lower():
            raise CloudChecksumMismatchError(
                f"Checksum mismatch for '{key}': expected {expected_sha256}, got {computed_sha}",
                provider="mock",
                status_code=400
            )

        etag = f'"{hashlib.md5(raw_bytes).hexdigest()}"'
        now = datetime.datetime.now(datetime.timezone.utc)

        self._objects[key] = {
            "data": raw_bytes,
            "size": len(raw_bytes),
            "sha256": computed_sha,
            "etag": etag,
            "metadata": metadata or {},
            "modified_at": now,
            "lock": None
        }

        return {
            "key": key,
            "size": len(raw_bytes),
            "sha256": computed_sha,
            "etag": etag,
            "modified_at": now.isoformat()
        }

    def download_object(self, key: str) -> bytes:
        if key not in self._objects:
            raise CloudObjectNotFoundError(f"Object '{key}' not found", provider="mock", status_code=404)
        return self._objects[key]["data"]

    def head_object(self, key: str) -> Dict[str, Any]:
        if key not in self._objects:
            raise CloudObjectNotFoundError(f"Object '{key}' not found", provider="mock", status_code=404)

        obj = self._objects[key]
        sha = obj["sha256"]
        if self.fail_next_verify:
            self.fail_next_verify = False
            sha = "mismatched_sha256_verification_fail"

        return {
            "key": key,
            "size": obj["size"],
            "sha256": sha,
            "etag": obj["etag"],
            "modified_at": obj["modified_at"],
            "metadata": obj["metadata"],
            "lock": obj["lock"]
        }

    def delete_object(self, key: str) -> bool:
        if key not in self._objects:
            return True

        obj = self._objects[key]
        lock = obj.get("lock")
        if lock:
            now = datetime.datetime.now(datetime.timezone.utc)
            retain_until = lock.get("retain_until")
            if retain_until and now < retain_until:
                mode = lock.get("mode", "GOVERNANCE")
                raise CloudObjectLockError(
                    f"Cannot delete object '{key}': WORM Object Lock in effect until {retain_until} (Mode: {mode})",
                    provider="mock",
                    status_code=403
                )

        del self._objects[key]
        return True

    def object_exists(self, key: str) -> bool:
        return key in self._objects

    def list_objects(self, prefix: str = "", limit: int = 1000) -> List[Dict[str, Any]]:
        results = []
        for k, v in self._objects.items():
            if k.startswith(prefix):
                results.append({
                    "key": k,
                    "size": v["size"],
                    "sha256": v["sha256"],
                    "etag": v["etag"],
                    "modified_at": v["modified_at"]
                })
                if len(results) >= limit:
                    break
        return results

    def supports_object_lock(self) -> bool:
        return self._supports_lock

    def set_object_lock(
        self,
        key: str,
        mode: str,
        retain_until_date: datetime.datetime
    ) -> bool:
        if not self._supports_lock:
            raise CloudObjectLockError(
                "Object Lock is not supported or enabled on this storage tier",
                provider="mock",
                status_code=400
            )
        if key not in self._objects:
            raise CloudObjectNotFoundError(f"Object '{key}' not found", provider="mock", status_code=404)

        if mode not in ["GOVERNANCE", "COMPLIANCE"]:
            raise CloudObjectLockError(f"Invalid immutability mode '{mode}'. Must be GOVERNANCE or COMPLIANCE.")

        self._objects[key]["lock"] = {
            "mode": mode,
            "retain_until": retain_until_date
        }
        return True
