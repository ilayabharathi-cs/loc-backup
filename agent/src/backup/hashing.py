"""Streaming incremental SHA-256 calculation for large and small files."""

import hashlib
from typing import Tuple, Optional


DEFAULT_HASH_CHUNK_SIZE = 4 * 1024 * 1024  # 4 MB


def calculate_file_sha256(
    file_path: str,
    chunk_size: int = DEFAULT_HASH_CHUNK_SIZE
) -> Tuple[str, int]:
    """
    Calculate SHA-256 hex digest and total byte count using streaming chunks.
    Does not load entire file into memory.
    Returns: (hex_sha256, total_bytes)
    """
    hasher = hashlib.sha256()
    total_bytes = 0

    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
            total_bytes += len(chunk)

    return hasher.hexdigest(), total_bytes
