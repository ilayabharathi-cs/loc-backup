"""Streaming compression and decompression service for RetroVault V5 Storage Engine.

Supports Zstandard (zstd) with configurable levels, Gzip, and raw pass-through (NONE).
Features automatic bypass for incompressible extensions and small files.
"""

import gzip
import hashlib
import os
import shutil
from typing import Generator, Optional, Tuple

try:
    import zstandard as zstd
    ZSTD_AVAILABLE = True
except ImportError:
    ZSTD_AVAILABLE = False


INCOMPRESSIBLE_EXTENSIONS = {
    # Archives / Compressed files
    ".zip", ".gz", ".tar", ".tgz", ".7z", ".rar", ".bz2", ".xz", ".zst",
    # Images
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".tiff",
    # Video / Audio
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".mp3", ".wav", ".flac", ".aac", ".ogg",
    # Pre-compressed documents
    ".pdf", ".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp",
}


def should_compress(file_path: Optional[str], size: int, min_size: int = 256) -> bool:
    """
    Determine if a file should be compressed based on size and extension.
    Files smaller than min_size or matching incompressible extensions are skipped.
    """
    if size < min_size:
        return False
    if not file_path:
        return True
    _, ext = os.path.splitext(file_path.lower())
    return ext not in INCOMPRESSIBLE_EXTENSIONS


def compress_file(
    source_path: str,
    dest_path: str,
    algorithm: str = "ZSTD",
    level: int = 3,
    chunk_size: int = 65536,
) -> Tuple[int, str, float]:
    """
    Compress a source file into a destination file.
    Returns:
        (stored_size, stored_sha256, compression_ratio)
    """
    algo = algorithm.upper()
    if algo == "ZSTD" and not ZSTD_AVAILABLE:
        algo = "GZIP"

    original_size = os.path.getsize(source_path)
    if original_size == 0 or algo == "NONE":
        # Raw copy
        hasher = hashlib.sha256()
        with open(source_path, "rb") as f_in, open(dest_path, "wb") as f_out:
            while chunk := f_in.read(chunk_size):
                hasher.update(chunk)
                f_out.write(chunk)
        stored_size = os.path.getsize(dest_path)
        stored_sha256 = hasher.hexdigest()
        return stored_size, stored_sha256, 1.0

    hasher = hashlib.sha256()
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

    if algo == "ZSTD":
        cctx = zstd.ZstdCompressor(level=level)
        with open(dest_path, "wb") as f_out:
            with cctx.stream_writer(f_out, closefd=False) as writer:
                with open(source_path, "rb") as f_in:
                    while chunk := f_in.read(chunk_size):
                        writer.write(chunk)
        # Compute stored sha256
        with open(dest_path, "rb") as f_out:
            while chunk := f_out.read(chunk_size):
                hasher.update(chunk)
    elif algo == "GZIP":
        with gzip.open(dest_path, "wb", compresslevel=6) as f_out:
            with open(source_path, "rb") as f_in:
                while chunk := f_in.read(chunk_size):
                    f_out.write(chunk)
        with open(dest_path, "rb") as f_out:
            while chunk := f_out.read(chunk_size):
                hasher.update(chunk)
    else:
        raise ValueError(f"Unsupported compression algorithm: {algorithm}")

    stored_size = os.path.getsize(dest_path)
    stored_sha256 = hasher.hexdigest()

    # Safety check: if compression actually expanded the file significantly, caller might fall back,
    # but ratio accounts for actual savings
    ratio = round(original_size / stored_size, 4) if stored_size > 0 else 1.0
    return stored_size, stored_sha256, ratio


def decompress_to_file(
    source_path: str,
    dest_path: str,
    algorithm: str = "NONE",
    chunk_size: int = 65536,
) -> Tuple[int, str]:
    """
    Decompress a stored object into destination file.
    Returns:
        (original_size, content_sha256)
    """
    algo = algorithm.upper()
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    hasher = hashlib.sha256()

    if algo == "NONE":
        with open(source_path, "rb") as f_in, open(dest_path, "wb") as f_out:
            while chunk := f_in.read(chunk_size):
                hasher.update(chunk)
                f_out.write(chunk)
    elif algo == "ZSTD":
        if not ZSTD_AVAILABLE:
            raise RuntimeError("zstandard library is required for ZSTD decompression")
        dctx = zstd.ZstdDecompressor()
        with open(source_path, "rb") as f_in:
            with dctx.stream_reader(f_in, closefd=False) as reader:
                with open(dest_path, "wb") as f_out:
                    while chunk := reader.read(chunk_size):
                        hasher.update(chunk)
                        f_out.write(chunk)
    elif algo == "GZIP":
        with gzip.open(source_path, "rb") as f_in, open(dest_path, "wb") as f_out:
            while chunk := f_in.read(chunk_size):
                hasher.update(chunk)
                f_out.write(chunk)
    else:
        raise ValueError(f"Unsupported decompression algorithm: {algorithm}")

    original_size = os.path.getsize(dest_path)
    return original_size, hasher.hexdigest()


def decompress_stream(
    source_path: str,
    algorithm: str = "NONE",
    chunk_size: int = 65536,
) -> Generator[bytes, None, None]:
    """
    Yield uncompressed chunks from a stored object.
    Ideal for streaming file downloads and restores.
    """
    algo = algorithm.upper()
    if algo == "NONE":
        with open(source_path, "rb") as f:
            while chunk := f.read(chunk_size):
                yield chunk
    elif algo == "ZSTD":
        if not ZSTD_AVAILABLE:
            raise RuntimeError("zstandard library is required for ZSTD decompression")
        dctx = zstd.ZstdDecompressor()
        with open(source_path, "rb") as f_in:
            with dctx.stream_reader(f_in, closefd=False) as reader:
                while chunk := reader.read(chunk_size):
                    yield chunk
    elif algo == "GZIP":
        with gzip.open(source_path, "rb") as f:
            while chunk := f.read(chunk_size):
                yield chunk
    else:
        raise ValueError(f"Unsupported decompression algorithm: {algorithm}")


def verify_stored_integrity(
    source_path: str,
    algorithm: str,
    expected_stored_sha256: str,
    expected_content_sha256: Optional[str] = None,
    chunk_size: int = 65536,
) -> Tuple[bool, str]:
    """
    Verify stored physical object integrity:
    1. Check stored file hash against expected_stored_sha256.
    2. Decompress stream and verify original content sha256 against expected_content_sha256 (if provided).
    Returns:
        (is_valid, error_reason)
    """
    if not os.path.exists(source_path):
        return False, f"File does not exist: {source_path}"

    stored_hasher = hashlib.sha256()
    with open(source_path, "rb") as f:
        while chunk := f.read(chunk_size):
            stored_hasher.update(chunk)

    computed_stored_sha = stored_hasher.hexdigest()
    if computed_stored_sha.lower() != expected_stored_sha256.lower():
        return False, f"Stored checksum mismatch: expected {expected_stored_sha256}, got {computed_stored_sha}"

    if expected_content_sha256:
        content_hasher = hashlib.sha256()
        try:
            for chunk in decompress_stream(source_path, algorithm=algorithm, chunk_size=chunk_size):
                content_hasher.update(chunk)
        except Exception as e:
            return False, f"Decompression error during integrity check: {e}"

        computed_content_sha = content_hasher.hexdigest()
        if computed_content_sha.lower() != expected_content_sha256.lower():
            return False, f"Content checksum mismatch: expected {expected_content_sha256}, got {computed_content_sha}"

    return True, "VALID"
