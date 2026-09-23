"""RetroVault Change Detection Engine V3.

Classifies filesystem state against baseline metadata into:
NEW, MODIFIED, UNCHANGED, DELETED, CHANGED_DURING_BACKUP, FAILED.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
import os
import datetime

from agent.src.backup.models import DiscoveredFile
from agent.src.backup.hashing import calculate_file_sha256
from agent.src.logger import get_logger


class FileState(str, Enum):
    """File classification states in RetroVault V3."""
    NEW = "NEW"
    MODIFIED = "MODIFIED"
    UNCHANGED = "UNCHANGED"
    DELETED = "DELETED"
    CHANGED_DURING_BACKUP = "CHANGED_DURING_BACKUP"
    FAILED = "FAILED"


@dataclass
class PreviousFileMetadata:
    """Represents a file from a baseline Recovery Point manifest."""
    id: Optional[int]
    file_name: str
    original_path: str
    relative_path: Optional[str]
    size_bytes: int
    sha256: Optional[str]
    storage_object: Optional[str]
    change_type: str
    upload_status: str
    modified_time: Optional[float] = None


@dataclass
class ClassifiedFile:
    """A file discovered in current scan or detected as deleted, with state."""
    state: FileState
    file_name: str
    original_path: str
    relative_path: Optional[str]
    size_bytes: int
    modified_time: float
    sha256: Optional[str] = None
    storage_object: Optional[str] = None
    discovered_file: Optional[DiscoveredFile] = None
    error_message: Optional[str] = None


@dataclass
class ChangeDetectionResult:
    """Summary of change detection against baseline recovery point."""
    new_files: List[ClassifiedFile] = field(default_factory=list)
    modified_files: List[ClassifiedFile] = field(default_factory=list)
    unchanged_files: List[ClassifiedFile] = field(default_factory=list)
    deleted_files: List[ClassifiedFile] = field(default_factory=list)
    failed_files: List[ClassifiedFile] = field(default_factory=list)

    @property
    def total_discovered(self) -> int:
        return len(self.new_files) + len(self.modified_files) + len(self.unchanged_files) + len(self.failed_files)

    @property
    def files_to_upload(self) -> List[ClassifiedFile]:
        """Only NEW and MODIFIED files require network data transfer."""
        return self.new_files + self.modified_files

    @property
    def upload_bytes(self) -> int:
        return sum(f.size_bytes for f in self.files_to_upload)

    @property
    def total_logical_bytes(self) -> int:
        """Total logical protected bytes (excluding deleted files)."""
        active = self.new_files + self.modified_files + self.unchanged_files
        return sum(f.size_bytes for f in active)


def _normalize_path_key(path_str: Optional[str]) -> str:
    """Normalize path for cross-platform and case-insensitive comparison."""
    if not path_str:
        return ""
    # Normalize forward slashes and lower-case on Windows
    norm = path_str.replace("\\", "/").strip("/").lower()
    return norm


def _parse_timestamp(val: Any) -> Optional[float]:
    """Parse float, int, datetime, or ISO string into unix timestamp float (UTC-aware)."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, datetime.datetime):
        if val.tzinfo is None:
            val = val.replace(tzinfo=datetime.timezone.utc)
        return val.timestamp()
    if isinstance(val, str):
        try:
            # Try float conversion first
            return float(val)
        except ValueError:
            pass
        try:
            dt = datetime.datetime.fromisoformat(val)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            return dt.timestamp()
        except Exception:
            return None
    return None


class ChangeDetector:
    """
    High-performance change detection engine.
    Uses size + mtime as fast primary change-detection mechanism.
    Only computes SHA-256 when file appears modified, ambiguous, or explicitly configured.
    """

    def __init__(self, mode: str = "metadata"):
        """
        mode:
          - 'metadata': fast size + mtime comparison (default, low CPU)
          - 'metadata_hash_verify': verifies SHA-256 for all candidate unchanged files
        """
        self.mode = mode
        self.logger = get_logger()

    def detect_changes(
        self,
        current_files: List[DiscoveredFile],
        baseline_manifest_files: List[Dict[str, Any]]
    ) -> ChangeDetectionResult:
        """
        Compare current discovered filesystem against baseline recovery point manifest.
        Returns classified files across NEW, MODIFIED, UNCHANGED, DELETED.
        """
        result = ChangeDetectionResult()

        # 1. Build map of previous active files (ignore previous deleted tombstones)
        previous_map: Dict[str, PreviousFileMetadata] = {}
        for entry in baseline_manifest_files:
            c_type = (entry.get("change_type") or "").upper()
            if c_type == "DELETED":
                continue

            rel_p = entry.get("relative_path")
            orig_p = entry.get("original_path")
            key = _normalize_path_key(rel_p) or _normalize_path_key(orig_p)
            if not key:
                continue

            mtime_val = _parse_timestamp(entry.get("modified_time"))
            prev_meta = PreviousFileMetadata(
                id=entry.get("id"),
                file_name=entry.get("file_name") or os.path.basename(orig_p or ""),
                original_path=orig_p or "",
                relative_path=rel_p,
                size_bytes=int(entry.get("size_bytes") or 0),
                sha256=entry.get("sha256"),
                storage_object=entry.get("storage_object"),
                change_type=c_type,
                upload_status=entry.get("upload_status") or "completed",
                modified_time=mtime_val
            )
            previous_map[key] = prev_meta

        # 2. Build current file map and track matches
        current_keys_seen = set()

        for curr in current_files:
            if not curr.is_accessible:
                classified = ClassifiedFile(
                    state=FileState.FAILED,
                    file_name=curr.file_name,
                    original_path=curr.original_path,
                    relative_path=curr.relative_path,
                    size_bytes=curr.size_bytes,
                    modified_time=curr.modified_time,
                    discovered_file=curr,
                    error_message=curr.error_message or "File inaccessible"
                )
                result.failed_files.append(classified)
                continue

            key = _normalize_path_key(curr.relative_path) or _normalize_path_key(curr.original_path)
            current_keys_seen.add(key)

            if key not in previous_map:
                # NEW file
                classified = ClassifiedFile(
                    state=FileState.NEW,
                    file_name=curr.file_name,
                    original_path=curr.original_path,
                    relative_path=curr.relative_path,
                    size_bytes=curr.size_bytes,
                    modified_time=curr.modified_time,
                    discovered_file=curr
                )
                result.new_files.append(classified)
            else:
                # File existed in baseline: compare metadata
                prev_meta = previous_map[key]
                is_changed = False

                # Size check
                if curr.size_bytes != prev_meta.size_bytes:
                    is_changed = True
                else:
                    # Modified time check (allow 1s tolerance for FAT/NTFS timestamp precision)
                    if prev_meta.modified_time is not None:
                        time_diff = abs(curr.modified_time - prev_meta.modified_time)
                        if time_diff > 1.0:
                            is_changed = True

                # Optional hash verification mode
                if not is_changed and self.mode == "metadata_hash_verify":
                    try:
                        computed_sha, _ = calculate_file_sha256(curr.original_path)
                        if prev_meta.sha256 and computed_sha.lower() != prev_meta.sha256.lower():
                            is_changed = True
                    except Exception as e:
                        self.logger.warning(f"Error computing hash verification for '{curr.file_name}': {e}")
                        is_changed = True

                if is_changed:
                    # MODIFIED file
                    classified = ClassifiedFile(
                        state=FileState.MODIFIED,
                        file_name=curr.file_name,
                        original_path=curr.original_path,
                        relative_path=curr.relative_path,
                        size_bytes=curr.size_bytes,
                        modified_time=curr.modified_time,
                        discovered_file=curr
                    )
                    result.modified_files.append(classified)
                else:
                    # UNCHANGED file: reuse previous immutable object reference and SHA-256!
                    classified = ClassifiedFile(
                        state=FileState.UNCHANGED,
                        file_name=curr.file_name,
                        original_path=curr.original_path,
                        relative_path=curr.relative_path,
                        size_bytes=curr.size_bytes,
                        modified_time=curr.modified_time,
                        sha256=prev_meta.sha256,
                        storage_object=prev_meta.storage_object,
                        discovered_file=curr
                    )
                    result.unchanged_files.append(classified)

        # 3. Detect DELETED files: baseline active files not in current scan
        for prev_key, prev_meta in previous_map.items():
            if prev_key not in current_keys_seen:
                classified = ClassifiedFile(
                    state=FileState.DELETED,
                    file_name=prev_meta.file_name,
                    original_path=prev_meta.original_path,
                    relative_path=prev_meta.relative_path,
                    size_bytes=prev_meta.size_bytes,
                    modified_time=prev_meta.modified_time or 0.0,
                    sha256=prev_meta.sha256,
                    storage_object=None
                )
                result.deleted_files.append(classified)

        self.logger.info(
            f"Change detection completed: {result.total_discovered} scanned | "
            f"NEW: {len(result.new_files)}, MODIFIED: {len(result.modified_files)}, "
            f"UNCHANGED: {len(result.unchanged_files)}, DELETED: {len(result.deleted_files)}, "
            f"FAILED: {len(result.failed_files)}."
        )

        return result
