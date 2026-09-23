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

    def get_staging_path(self, client_identifier: str, run_id: int, session_id: str) -> str:
        """Compute absolute path for staging an in-progress resumable upload session."""
        safe_client = self._sanitize_identifier(client_identifier, "client_id")
        safe_run = self._sanitize_identifier(str(run_id), "run_id")
        safe_session = self._sanitize_identifier(session_id, "session_id")

        staging_dir = os.path.join(self.root_path, "clients", safe_client, "runs", safe_run, "staging")
        os.makedirs(staging_dir, exist_ok=True)
        return os.path.join(staging_dir, f"{safe_session}.part")

    def write_staging_chunk(
        self,
        client_identifier: str,
        run_id: int,
        session_id: str,
        offset: int,
        chunk_bytes: bytes
    ) -> int:
        """Write chunk bytes at exact byte offset into the session's staging file."""
        staging_file = self.get_staging_path(client_identifier, run_id, session_id)
        mode = "r+b" if os.path.exists(staging_file) else "wb"
        with open(staging_file, mode) as f:
            f.seek(offset)
            f.write(chunk_bytes)
            f.flush()
        return len(chunk_bytes)

    def finalize_staging_object(
        self,
        client_identifier: str,
        run_id: int,
        session_id: str,
        object_id: str,
        expected_sha256: Optional[str] = None
    ) -> Tuple[str, int, str]:
        """
        Verify the completed staging file SHA-256 and atomically move to final repository location.
        Returns: (storage_object_rel_path, bytes_written, computed_sha256)
        """
        staging_file = self.get_staging_path(client_identifier, run_id, session_id)
        if not os.path.exists(staging_file):
            raise FileNotFoundError(f"Staging file not found for session {session_id}")

        final_path = self.get_object_path(client_identifier, run_id, object_id)

        hasher = hashlib.sha256()
        total_bytes = 0
        chunk_size = 4 * 1024 * 1024
        with open(staging_file, "rb") as f:
            while True:
                buf = f.read(chunk_size)
                if not buf:
                    break
                hasher.update(buf)
                total_bytes += len(buf)

        computed_hash = hasher.hexdigest()
        if expected_sha256 and expected_sha256.lower() != computed_hash.lower():
            raise ValueError(
                f"Full file SHA-256 mismatch for object {object_id}: "
                f"expected {expected_sha256}, calculated {computed_hash}"
            )

        os.replace(staging_file, final_path)
        rel_path = os.path.relpath(final_path, self.root_path).replace("\\", "/")
        return rel_path, total_bytes, computed_hash

    # =========================================================================
    # V5 Content-Addressed Storage (CAS), Compression & Deduplication Engine
    # =========================================================================

    def get_cas_path(self, content_sha256: str) -> str:
        """Compute absolute path for a content-addressed storage object."""
        sha = content_sha256.lower().strip()
        if not SAFE_ID_PATTERN.match(sha) or len(sha) < 4:
            raise ValueError(f"Invalid SHA-256 format for CAS: '{content_sha256}'")

        dir_path = os.path.join(self.root_path, "objects", sha[:2], sha[2:4])
        norm_root = os.path.normcase(os.path.abspath(self.root_path))
        norm_dir = os.path.normcase(os.path.abspath(dir_path))
        if not norm_dir.startswith(norm_root):
            raise ValueError(f"Path traversal detected in CAS path: '{content_sha256}'")

        os.makedirs(dir_path, exist_ok=True)
        return os.path.join(dir_path, sha)

    def cas_object_exists(self, content_sha256: str) -> bool:
        """Check if a content-addressed physical object already exists on disk."""
        target_file = self.get_cas_path(content_sha256)
        return os.path.isfile(target_file) and os.path.getsize(target_file) > 0

    def store_cas_object(
        self,
        source_path_or_bytes: Union[str, bytes, BinaryIO],
        content_sha256: str,
        original_size: int,
        filename_hint: Optional[str] = None,
        compress: bool = True,
        compression_level: int = 3,
    ) -> Tuple[str, int, str, str, float]:
        """
        Store a deduplicated content-addressed object into repository CAS layout.
        Returns:
            (rel_path, stored_size, stored_sha256, compression_algorithm, compression_ratio)
        """
        from app.services.compression import compress_file, should_compress

        target_file = self.get_cas_path(content_sha256)
        rel_path = os.path.relpath(target_file, self.root_path).replace("\\", "/")

        # Check if already present physically
        if os.path.isfile(target_file) and os.path.getsize(target_file) > 0:
            stored_size = os.path.getsize(target_file)
            # Recompute stored sha for returning accurate stats
            h = hashlib.sha256()
            with open(target_file, "rb") as f:
                while chunk := f.read(65536):
                    h.update(chunk)
            stored_sha = h.hexdigest()
            ratio = round(original_size / stored_size, 4) if stored_size > 0 else 1.0
            return rel_path, stored_size, stored_sha, "ZSTD" if stored_size < original_size else "NONE", ratio

        # Determine compression
        use_compression = compress and should_compress(filename_hint, original_size)
        algo = "ZSTD" if use_compression else "NONE"

        # Prepare source as file on disk
        temp_dir = os.path.join(self.root_path, "objects", ".staging")
        os.makedirs(temp_dir, exist_ok=True)

        if isinstance(source_path_or_bytes, str) and os.path.isfile(source_path_or_bytes):
            src_file = source_path_or_bytes
            cleanup_src = False
        else:
            fd, src_file = tempfile.mkstemp(dir=temp_dir, prefix=".tmp_in_")
            cleanup_src = True
            with os.fdopen(fd, "wb") as f_tmp:
                if isinstance(source_path_or_bytes, bytes):
                    f_tmp.write(source_path_or_bytes)
                else:
                    while chunk := source_path_or_bytes.read(65536):
                        f_tmp.write(chunk)

        fd_out, tmp_out = tempfile.mkstemp(dir=temp_dir, prefix=".tmp_cas_")
        os.close(fd_out)

        try:
            stored_size, stored_sha256, ratio = compress_file(
                src_file,
                tmp_out,
                algorithm=algo,
                level=compression_level,
            )
            # Atomic replace into final CAS target
            os.replace(tmp_out, target_file)
            return rel_path, stored_size, stored_sha256, algo, ratio
        finally:
            if cleanup_src and os.path.exists(src_file):
                try:
                    os.remove(src_file)
                except OSError:
                    pass
            if os.path.exists(tmp_out):
                try:
                    os.remove(tmp_out)
                except OSError:
                    pass

    def finalize_staging_cas_object(
        self,
        staging_file: str,
        content_sha256: str,
        original_size: int,
        filename_hint: Optional[str] = None,
        compress: bool = True,
        compression_level: int = 3,
    ) -> Tuple[str, int, str, str, float]:
        """
        Convert a completed session staging file into an immutable CAS object.
        Deletes staging file upon success.
        """
        try:
            res = self.store_cas_object(
                source_path_or_bytes=staging_file,
                content_sha256=content_sha256,
                original_size=original_size,
                filename_hint=filename_hint,
                compress=compress,
                compression_level=compression_level,
            )
            return res
        finally:
            if os.path.exists(staging_file):
                try:
                    os.remove(staging_file)
                except OSError:
                    pass

    def resolve_stored_path(self, relative_or_absolute_path: str) -> str:
        """Resolve storage path whether it's relative to root or absolute."""
        if os.path.isabs(relative_or_absolute_path):
            return relative_or_absolute_path
        return os.path.join(self.root_path, relative_or_absolute_path)

    def read_object_stream(
        self,
        relative_or_absolute_path: str,
        compression_algorithm: str = "NONE",
        chunk_size: int = 65536,
    ):
        """Yield uncompressed byte chunks from a stored object (V1-V5 compatible)."""
        from app.services.compression import decompress_stream
        full_path = self.resolve_stored_path(relative_or_absolute_path)
        if not os.path.isfile(full_path):
            raise FileNotFoundError(f"Storage object file not found: {full_path}")
        return decompress_stream(full_path, algorithm=compression_algorithm, chunk_size=chunk_size)

    def quarantine_object(self, relative_or_absolute_path: str, reason: str = "CORRUPTED") -> str:
        """Move corrupted or failing physical object to quarantine directory for isolation."""
        full_path = self.resolve_stored_path(relative_or_absolute_path)
        if not os.path.isfile(full_path):
            return ""

        quarantine_dir = os.path.join(self.root_path, "quarantine")
        os.makedirs(quarantine_dir, exist_ok=True)
        fname = os.path.basename(full_path)
        safe_reason = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", reason)[:40]
        quarantine_path = os.path.join(quarantine_dir, f"{fname}_{safe_reason}.bad")
        shutil.move(full_path, quarantine_path)
        return quarantine_path

    def physical_delete_object(self, relative_or_absolute_path: str) -> bool:
        """Physically delete a file from disk if present."""
        full_path = self.resolve_stored_path(relative_or_absolute_path)
        if os.path.isfile(full_path):
            try:
                os.remove(full_path)
                return True
            except OSError:
                return False
        return False

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
