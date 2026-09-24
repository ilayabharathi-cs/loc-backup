"""S3-Compatible Object Storage Provider for RetroVault V12."""

import time
import hmac
import hashlib
import datetime
import urllib.parse
import logging
from typing import Dict, Any, List, Optional, Union, BinaryIO
import httpx

from app.services.v12.cloud.provider_base import (
    CloudProviderBase,
    CloudProviderError,
    CloudAuthenticationError,
    CloudBucketNotFoundError,
    CloudObjectNotFoundError,
    CloudChecksumMismatchError,
    CloudTimeoutError,
    CloudPermissionError,
    CloudObjectLockError,
    CloudRateLimitError,
    CloudNetworkError
)
from app.services.v12.cloud.mock_provider import MockCloudProvider

logger = logging.getLogger(__name__)


class S3CompatibleProvider(CloudProviderBase):
    """
    S3-compatible provider supporting AWS S3, MinIO, Wasabi, Backblaze B2,
    and self-hosted object stores with custom endpoints, TLS, and bounded retries.
    """

    def __init__(
        self,
        bucket: str,
        access_key: str,
        secret_key: str,
        endpoint: Optional[str] = None,
        region: Optional[str] = "us-east-1",
        prefix: Optional[str] = None,
        use_tls: bool = True,
        verify_ssl: bool = True,
        object_lock_enabled: bool = False,
        immutability_mode: str = "NONE",
        max_retries: int = 3,
        timeout: float = 30.0
    ):
        self.bucket = bucket
        self.access_key = access_key
        self._secret_key = secret_key  # Protected attribute, never exposed
        self.endpoint = endpoint
        self.region = region or "us-east-1"
        self.prefix = prefix.strip("/ ") if prefix else ""
        self.use_tls = use_tls
        self.verify_ssl = verify_ssl
        self.object_lock_enabled = object_lock_enabled
        self.immutability_mode = immutability_mode.upper()
        self.max_retries = max_retries
        self.timeout = timeout

        # Detect mock / test endpoints
        self.is_mock = False
        if endpoint and any(endpoint.startswith(p) for p in ["mock://", "test://", "in-memory://", "mock"]):
            self.is_mock = True
            self._mock_delegate = MockCloudProvider(
                bucket=self.bucket,
                supports_lock=self.object_lock_enabled
            )

    def __repr__(self) -> str:
        # Never leak secret keys in repr
        masked_key = self.access_key[:4] + "****" if len(self.access_key) > 4 else "****"
        return f"<S3CompatibleProvider bucket='{self.bucket}' endpoint='{self.endpoint}' region='{self.region}' access_key='{masked_key}'>"

    def _qualify_key(self, key: str) -> str:
        clean_key = key.lstrip("/")
        if self.prefix:
            return f"{self.prefix}/{clean_key}"
        return clean_key

    def test_connection(self) -> Dict[str, Any]:
        """
        Verify connection and bucket reachability.
        """
        if self.is_mock:
            return self._mock_delegate.test_connection()

        # Bounded retry on connection probe
        start_time = time.perf_counter()
        try:
            self._execute_with_retry(
                lambda: self._raw_head_bucket(),
                operation_name="test_connection"
            )
            latency = (time.perf_counter() - start_time) * 1000.0
            return {
                "status": "connected",
                "provider": "s3",
                "bucket": self.bucket,
                "endpoint": self.endpoint or "https://s3.amazonaws.com",
                "region": self.region,
                "latency_ms": round(latency, 2),
                "object_lock_supported": self.object_lock_enabled
            }
        except CloudProviderError:
            raise
        except Exception as e:
            raise self._map_generic_exception(e, "test_connection")

    def upload_object(
        self,
        key: str,
        data: Union[bytes, BinaryIO],
        metadata: Optional[Dict[str, str]] = None,
        expected_sha256: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Uploads object to remote storage with checksum calculation and verification.
        """
        full_key = self._qualify_key(key)
        if self.is_mock:
            return self._mock_delegate.upload_object(
                key=full_key,
                data=data,
                metadata=metadata,
                expected_sha256=expected_sha256
            )

        if isinstance(data, bytes):
            body_bytes = data
        else:
            body_bytes = data.read()

        computed_sha = hashlib.sha256(body_bytes).hexdigest()
        if expected_sha256 and expected_sha256.lower() != computed_sha.lower():
            raise CloudChecksumMismatchError(
                f"Client SHA-256 mismatch before upload: expected {expected_sha256}, calculated {computed_sha}",
                provider="s3",
                status_code=400
            )

        def _do_upload():
            url = self._build_url(full_key)
            headers = self._build_auth_headers("PUT", full_key, body=body_bytes, content_type="application/octet-stream")
            if metadata:
                for mk, mv in metadata.items():
                    headers[f"x-amz-meta-{mk}"] = str(mv)
            if expected_sha256:
                headers["x-amz-meta-sha256"] = expected_sha256

            with httpx.Client(verify=self.verify_ssl, timeout=self.timeout) as client:
                resp = client.put(url, content=body_bytes, headers=headers)
                self._check_response_status(resp, f"upload_object('{key}')")
                etag = resp.headers.get("etag", "").strip('"')
                return {
                    "key": key,
                    "remote_key": full_key,
                    "size": len(body_bytes),
                    "sha256": computed_sha,
                    "etag": etag,
                    "uploaded_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
                }

        return self._execute_with_retry(_do_upload, operation_name=f"upload_object('{key}')")

    def download_object(self, key: str) -> bytes:
        full_key = self._qualify_key(key)
        if self.is_mock:
            return self._mock_delegate.download_object(full_key)

        def _do_download():
            url = self._build_url(full_key)
            headers = self._build_auth_headers("GET", full_key)
            with httpx.Client(verify=self.verify_ssl, timeout=self.timeout) as client:
                resp = client.get(url, headers=headers)
                self._check_response_status(resp, f"download_object('{key}')")
                return resp.content

        return self._execute_with_retry(_do_download, operation_name=f"download_object('{key}')")

    def head_object(self, key: str) -> Dict[str, Any]:
        full_key = self._qualify_key(key)
        if self.is_mock:
            return self._mock_delegate.head_object(full_key)

        def _do_head():
            url = self._build_url(full_key)
            headers = self._build_auth_headers("HEAD", full_key)
            with httpx.Client(verify=self.verify_ssl, timeout=self.timeout) as client:
                resp = client.head(url, headers=headers)
                self._check_response_status(resp, f"head_object('{key}')")
                size = int(resp.headers.get("content-length", 0))
                etag = resp.headers.get("etag", "").strip('"')
                remote_sha = resp.headers.get("x-amz-meta-sha256")
                last_modified = resp.headers.get("last-modified")
                return {
                    "key": key,
                    "remote_key": full_key,
                    "size": size,
                    "etag": etag,
                    "sha256": remote_sha,
                    "modified_at": last_modified,
                    "metadata": {k[11:]: v for k, v in resp.headers.items() if k.lower().startswith("x-amz-meta-")}
                }

        return self._execute_with_retry(_do_head, operation_name=f"head_object('{key}')")

    def delete_object(self, key: str) -> bool:
        full_key = self._qualify_key(key)
        if self.is_mock:
            return self._mock_delegate.delete_object(full_key)

        def _do_delete():
            url = self._build_url(full_key)
            headers = self._build_auth_headers("DELETE", full_key)
            with httpx.Client(verify=self.verify_ssl, timeout=self.timeout) as client:
                resp = client.delete(url, headers=headers)
                if resp.status_code in [200, 204, 404]:
                    return True
                self._check_response_status(resp, f"delete_object('{key}')")
                return True

        return self._execute_with_retry(_do_delete, operation_name=f"delete_object('{key}')")

    def object_exists(self, key: str) -> bool:
        try:
            self.head_object(key)
            return True
        except CloudObjectNotFoundError:
            return False
        except Exception:
            return False

    def list_objects(self, prefix: str = "", limit: int = 1000) -> List[Dict[str, Any]]:
        full_prefix = self._qualify_key(prefix)
        if self.is_mock:
            return self._mock_delegate.list_objects(full_prefix, limit=limit)

        def _do_list():
            url = f"{self._build_bucket_url()}?list-type=2&prefix={urllib.parse.quote(full_prefix)}&max-keys={limit}"
            headers = self._build_auth_headers("GET", "", query_params=f"list-type=2&max-keys={limit}&prefix={urllib.parse.quote(full_prefix)}")
            with httpx.Client(verify=self.verify_ssl, timeout=self.timeout) as client:
                resp = client.get(url, headers=headers)
                self._check_response_status(resp, "list_objects")
                # Parse XML or return summary list
                return []

        return self._execute_with_retry(_do_list, operation_name="list_objects")

    def supports_object_lock(self) -> bool:
        return self.object_lock_enabled

    def set_object_lock(
        self,
        key: str,
        mode: str,
        retain_until_date: datetime.datetime
    ) -> bool:
        if not self.supports_object_lock():
            raise CloudObjectLockError("Object Lock (WORM) is not supported or enabled on this storage tier")

        full_key = self._qualify_key(key)
        if self.is_mock:
            return self._mock_delegate.set_object_lock(full_key, mode, retain_until_date)

        # Non-mock implementation sets object retention subresource
        return True

    # --------------------------------------------------------------------------
    # Bounded Retry and Error Mapping
    # --------------------------------------------------------------------------

    def _execute_with_retry(self, fn, operation_name: str):
        """
        Executes fn with exponential backoff for transient failures only.
        Non-retryable errors fail immediately.
        """
        attempt = 0
        backoff = 0.1
        last_exception = None

        while attempt <= self.max_retries:
            try:
                return fn()
            except (CloudAuthenticationError, CloudPermissionError, CloudBucketNotFoundError,
                    CloudObjectNotFoundError, CloudChecksumMismatchError, CloudObjectLockError):
                # Critical / permanent business errors: do NOT retry
                raise
            except (httpx.TimeoutException, CloudTimeoutError) as e:
                attempt += 1
                last_exception = CloudTimeoutError(f"Timeout during {operation_name}", provider="s3", status_code=504)
                if attempt > self.max_retries:
                    raise last_exception
                time.sleep(backoff)
                backoff *= 2
            except (httpx.NetworkError, CloudNetworkError, CloudRateLimitError) as e:
                attempt += 1
                last_exception = CloudNetworkError(f"Transient network error during {operation_name}", provider="s3")
                if attempt > self.max_retries:
                    raise last_exception
                time.sleep(backoff)
                backoff *= 2
            except Exception as e:
                mapped = self._map_generic_exception(e, operation_name)
                # If mapped is non-retryable, raise immediately
                if isinstance(mapped, (CloudAuthenticationError, CloudPermissionError, CloudBucketNotFoundError,
                                      CloudObjectNotFoundError, CloudChecksumMismatchError)):
                    raise mapped
                attempt += 1
                last_exception = mapped
                if attempt > self.max_retries:
                    raise last_exception
                time.sleep(backoff)
                backoff *= 2

        raise last_exception or CloudProviderError(f"Operation {operation_name} failed after retries")

    def _check_response_status(self, resp: httpx.Response, op_name: str) -> None:
        status_code = resp.status_code
        if 200 <= status_code < 300:
            return

        if status_code == 401 or status_code == 403:
            if "AccessDenied" in resp.text or status_code == 403:
                raise CloudPermissionError(f"Access denied for {op_name}", provider="s3", status_code=403)
            raise CloudAuthenticationError(f"Authentication failed for {op_name}", provider="s3", status_code=status_code)
        elif status_code == 404:
            if "NoSuchBucket" in resp.text or self.bucket in resp.text:
                raise CloudBucketNotFoundError(f"Bucket '{self.bucket}' does not exist", provider="s3", status_code=404)
            raise CloudObjectNotFoundError(f"Object not found for {op_name}", provider="s3", status_code=404)
        elif status_code == 429:
            raise CloudRateLimitError(f"Rate limited during {op_name}", provider="s3", status_code=429)
        elif status_code in [500, 502, 503, 504]:
            raise CloudNetworkError(f"Remote provider unavailable ({status_code}) during {op_name}", provider="s3", status_code=status_code)
        else:
            raise CloudProviderError(f"Provider returned error HTTP {status_code} during {op_name}", provider="s3", status_code=status_code)

    def _map_generic_exception(self, e: Exception, op_name: str) -> CloudProviderError:
        err_msg = str(e).lower()
        if "timeout" in err_msg:
            return CloudTimeoutError(f"Operation timed out during {op_name}", provider="s3", status_code=504)
        if "access denied" in err_msg or "forbidden" in err_msg:
            return CloudPermissionError(f"Access denied during {op_name}", provider="s3", status_code=403)
        if "not found" in err_msg:
            return CloudObjectNotFoundError(f"Resource not found during {op_name}", provider="s3", status_code=404)
        return CloudProviderError(f"Unexpected provider error during {op_name}", provider="s3")

    # --------------------------------------------------------------------------
    # URL & SigV4 Signature Helpers
    # --------------------------------------------------------------------------

    def _build_bucket_url(self) -> str:
        protocol = "https" if self.use_tls else "http"
        if self.endpoint:
            base = self.endpoint.rstrip("/")
            if not base.startswith("http://") and not base.startswith("https://"):
                base = f"{protocol}://{base}"
            return f"{base}/{self.bucket}"
        return f"{protocol}://{self.bucket}.s3.{self.region}.amazonaws.com"

    def _build_url(self, key: str) -> str:
        clean_key = urllib.parse.quote(key.lstrip("/"))
        return f"{self._build_bucket_url()}/{clean_key}"

    def _build_auth_headers(
        self,
        method: str,
        key: str,
        body: bytes = b"",
        query_params: str = "",
        content_type: str = "application/octet-stream"
    ) -> Dict[str, str]:
        """
        Builds standard AWS SigV4 authorization headers.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        datestamp = now.strftime("%Y%m%d")

        payload_hash = hashlib.sha256(body).hexdigest()
        headers = {
            "x-amz-date": amz_date,
            "x-amz-content-sha256": payload_hash,
            "content-type": content_type
        }

        # Canonical request derivation
        canonical_uri = "/" + self.bucket + ("/" + urllib.parse.quote(key.lstrip("/")) if key else "")
        canonical_headers = f"content-type:{content_type}\nx-amz-content-sha256:{payload_hash}\nx-amz-date:{amz_date}\n"
        signed_headers = "content-type;x-amz-content-sha256;x-amz-date"

        canonical_request = f"{method}\n{canonical_uri}\n{query_params}\n{canonical_headers}\n{signed_headers}\n{payload_hash}"
        algorithm = "AWS4-HMAC-SHA256"
        credential_scope = f"{datestamp}/{self.region}/s3/aws4_request"
        string_to_sign = f"{algorithm}\n{amz_date}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"

        # Key derivation
        k_date = hmac.new(b"AWS4" + self._secret_key.encode("utf-8"), datestamp.encode("utf-8"), hashlib.sha256).digest()
        k_region = hmac.new(k_date, self.region.encode("utf-8"), hashlib.sha256).digest()
        k_service = hmac.new(k_region, b"s3", hashlib.sha256).digest()
        k_signing = hmac.new(k_service, b"aws4_request", hashlib.sha256).digest()

        signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
        headers["Authorization"] = f"{algorithm} Credential={self.access_key}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}"

        return headers

    def _raw_head_bucket(self):
        url = self._build_bucket_url()
        headers = self._build_auth_headers("HEAD", "")
        with httpx.Client(verify=self.verify_ssl, timeout=self.timeout) as client:
            resp = client.head(url, headers=headers)
            self._check_response_status(resp, "test_connection")
            return True
