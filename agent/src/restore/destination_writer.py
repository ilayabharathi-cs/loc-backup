"""Secure Destination File Writer for RetroVault Windows Agent.

Features:
- Streaming writes in bounded 4 MB chunks.
- In-flight SHA-256 calculation.
- Safe atomic temporary file replacement (.tmp -> verify -> os.replace).
- Complete preservation of existing files on checksum mismatch.
- Integration with ConflictResolver and MetadataWriter.
"""

import os
import uuid
import hashlib
from typing import Iterator, Optional, Dict, Any, List

from agent.src.restore.path_validator import AgentPathValidator
from agent.src.restore.conflict_resolver import ConflictResolver, RestoreConflictError
from agent.src.restore.metadata_writer import MetadataWriter


class ChecksumMismatchError(Exception):
    """Raised when calculated destination SHA-256 does not match expected hash."""
    pass


class DestinationWriter:
    """Manages secure file streaming, hashing, atomic writing, and validation."""

    CHUNK_SIZE = 4 * 1024 * 1024  # 4 MB configurable streaming chunk

    @classmethod
    def write_stream_atomic(
        cls,
        destination_root: str,
        relative_path: str,
        stream_chunks: Iterator[bytes],
        expected_sha256: str,
        conflict_mode: str = "OVERWRITE",
        metadata_mode: str = "BASIC",
        modified_time: Optional[Any] = None,
        attributes: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Safely writes an incoming byte stream onto the destination path.
        Returns execution result dict.
        """
        # 1. Path safety and resolution
        target_path = AgentPathValidator.resolve_destination(destination_root, relative_path)

        # 2. Conflict evaluation
        action, final_path = ConflictResolver.resolve_target(target_path, conflict_mode)
        if action == "SKIP":
            return {
                "success": True,
                "action": "SKIPPED",
                "destination_path": final_path,
                "bytes_written": 0,
                "sha256": None,
                "warnings": []
            }

        # 3. Create destination directory
        dest_dir = os.path.dirname(final_path)
        os.makedirs(dest_dir, exist_ok=True)

        # 4. Create temporary sibling file
        tmp_filename = f".{os.path.basename(final_path)}.tmp.{uuid.uuid4().hex[:8]}"
        tmp_path = os.path.join(dest_dir, tmp_filename)

        hasher = hashlib.sha256()
        bytes_written = 0

        try:
            with open(tmp_path, "wb") as f:
                for chunk in stream_chunks:
                    f.write(chunk)
                    hasher.update(chunk)
                    bytes_written += len(chunk)
        except Exception as e:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise IOError(f"Write failed during stream to '{tmp_path}': {e}")

        # 5. Checksum verification
        computed_sha = hasher.hexdigest().lower()
        if expected_sha256 and computed_sha != expected_sha256.lower():
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise ChecksumMismatchError(
                f"Integrity check failed for '{relative_path}': expected {expected_sha256}, got {computed_sha}"
            )

        # 6. Atomic replacement
        os.replace(tmp_path, final_path)

        # 7. Apply metadata
        warnings = MetadataWriter.apply_metadata(
            final_path,
            metadata_mode=metadata_mode,
            modified_time=modified_time,
            attributes=attributes
        )

        return {
            "success": True,
            "action": "OVERWRITTEN" if action == "WRITE" and os.path.exists(target_path) else "CREATED",
            "destination_path": final_path,
            "bytes_written": bytes_written,
            "sha256": computed_sha,
            "warnings": warnings
        }
