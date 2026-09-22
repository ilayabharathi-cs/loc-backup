"""Local Filesystem Implementation of Backup Storage Repository."""

import os
import re
import shutil
import hashlib
import tempfile
from typing import BinaryIO, Dict, Any, Tuple, Union, Optional
from app.services.repository.base import StorageRepositoryBase
from app.config import settings


SAFE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.]+$")


class LocalFilesystemRepository(StorageRepositoryBase):
    """Stores immutable backup file objects on local or mounted storage."""

    def __init__(self, root_path: Optional[str] = None):
        self.root_path = os.path.abspath(root_path or settings.get_repository_root())
        os.makedirs(self.root_path, exist_ok=True)

    def _sanitize_identifier(self, value: str, name: str) -> str:
        """Ensure identifier contains only safe alphanumeric/dash characters."""
        cleaned = str(value).strip()
        if not cleaned or not SAFE_ID_PATTERN.match(cleaned):
            raise ValueError(f"Invalid {name} '{value}'. Must be alphanumeric with - or _.")
        return cleaned

    def _get_target_dir(self, client_identifier: str, run_id: int) -> str:
        """Compute and ensure target directory for a client run."""
        safe_client = self._sanitize_identifier(client_identifier, "client_id")
        safe_run = self._sanitize_identifier(str(run_id), "run_id")

        target_dir = os.path.join(self.root_path, "clients", safe_client, "runs", safe_run, "objects")
        # Security: verify target_dir remains inside repository root
        norm_root = os.path.normcase(os.path.abspath(self.root_path))
        norm_target = os.path.normcase(os.path.abspath(target_dir))
        if not norm_target.startswith(norm_root):
            raise ValueError(f"Directory traversal attack detected: '{client_identifier}'")

        os.makedirs(target_dir, exist_ok=True)
        return target_dir

    def get_object_path(self, client_identifier: str, run_id: int, object_id: str) -> str:
        """Compute absolute path to an object and verify boundary containment."""
        safe_obj = self._sanitize_identifier(object_id, "object_id")
        target_dir = self._get_target_dir(client_identifier, run_id)
        obj_path = os.path.join(target_dir, safe_obj)

        norm_dir = os.path.normcase(os.path.abspath(target_dir))
        norm_obj = os.path.normcase(os.path.abspath(obj_path))
        if not norm_obj.startswith(norm_dir):
            raise ValueError(f"Path traversal detected in object_id: '{object_id}'")

        return obj_path

    def object_exists(self, client_identifier: str, run_id: int, object_id: str) -> bool:
        """Check if an object exists on disk."""
        path = self.get_object_path(client_identifier, run_id, object_id)
        return os.path.exists(path) and os.path.isfile(path)

    def store_object(
        self,
        client_identifier: str,
        run_id: int,
        object_id: str,
        content: Union[bytes, BinaryIO],
        expected_sha256: Optional[str] = None
    ) -> Tuple[str, int, str]:
        """
        Store object with streaming SHA-256 calculation and atomic replace.
        Returns: (storage_object_rel_path, bytes_written, computed_sha256)
        """
        target_dir = self._get_target_dir(client_identifier, run_id)
        final_path = self.get_object_path(client_identifier, run_id, object_id)

        hasher = hashlib.sha256()
        bytes_written = 0

        # Write to temporary file in the same directory for atomic rename
        fd, tmp_path = tempfile.mkstemp(dir=target_dir, prefix=".tmp_upload_", suffix=".dat")
        try:
            with os.fdopen(fd, "wb") as f_out:
                if isinstance(content, bytes):
                    f_out.write(content)
                    hasher.update(content)
                    bytes_written = len(content)
                else:
                    # Stream chunks
                    chunk_size = 4 * 1024 * 1024  # 4 MB
                    while True:
                        chunk = content.read(chunk_size)
                        if not chunk:
                            break
                        f_out.write(chunk)
                        hasher.update(chunk)
                        bytes_written += len(chunk)

            computed_hash = hasher.hexdigest()

            # Verify integrity if client supplied expected SHA-256
            if expected_sha256 and expected_sha256.lower() != computed_hash.lower():
                raise ValueError(
                    f"SHA-256 mismatch for object {object_id}: "
                    f"expected {expected_sha256}, calculated {computed_hash}"
                )

            # Atomic replace
            os.replace(tmp_path, final_path)

            # Return relative path for database storage
            rel_path = os.path.relpath(final_path, self.root_path).replace("\\", "/")
            return rel_path, bytes_written, computed_hash

        except Exception:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            raise

    def validate_storage_health(self) -> Dict[str, Any]:
        """Check repository capacity and health status."""
        try:
            usage = shutil.disk_usage(self.root_path)
            # Test write access
            test_file = os.path.join(self.root_path, ".health_check.tmp")
            with open(test_file, "w") as f:
                f.write("ok")
            os.remove(test_file)

            return {
                "status": "healthy",
                "repository_root": self.root_path,
                "writable": True,
                "total_bytes": usage.total,
                "used_bytes": usage.used,
                "free_bytes": usage.free,
                "free_percent": round((usage.free / usage.total) * 100.0, 1) if usage.total > 0 else 0
            }
        except Exception as e:
            return {
                "status": "degraded",
                "repository_root": self.root_path,
                "writable": False,
                "error": str(e)
            }


_repository_instance: Optional[LocalFilesystemRepository] = None

def get_repository() -> LocalFilesystemRepository:
    """Retrieve singleton repository instance."""
    global _repository_instance
    if _repository_instance is None:
        _repository_instance = LocalFilesystemRepository()
    return _repository_instance
