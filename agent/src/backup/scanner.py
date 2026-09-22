"""Recursive directory scanner for RetroVault Backup Engine."""

import os
from typing import List, Set, Optional
from agent.src.backup.models import DiscoveredFile
from agent.src.utils.filesystem import canonicalize_path
from agent.src.logger import get_logger


class FileScanner:
    """Recursively discovers eligible backup files respecting policies and boundaries."""

    def __init__(self, include_paths: List[str], exclude_paths: Optional[List[str]] = None):
        self.include_paths = [canonicalize_path(p) for p in include_paths if p]
        self.exclude_paths = {canonicalize_path(p).lower() for p in (exclude_paths or []) if p}
        self.logger = get_logger()

    def _is_path_excluded(self, norm_path: str) -> bool:
        """Check if a path or any of its parents match the exclusion list."""
        path_lower = norm_path.lower()
        for exc in self.exclude_paths:
            if path_lower == exc or path_lower.startswith(exc.rstrip(os.sep) + os.sep):
                return True
        return False

    def scan(self) -> List[DiscoveredFile]:
        """Scan all configured include roots and return a deduplicated list of discovered files."""
        discovered: List[DiscoveredFile] = []
        seen_files: Set[str] = set()

        for root in self.include_paths:
            if not os.path.exists(root):
                self.logger.warning(f"Scan root does not exist: '{root}'")
                continue

            if self._is_path_excluded(root):
                self.logger.debug(f"Skipping excluded root: '{root}'")
                continue

            if os.path.isfile(root):
                # Single file root
                file_obj = self._process_file(root, os.path.dirname(root))
                if file_obj and file_obj.original_path.lower() not in seen_files:
                    seen_files.add(file_obj.original_path.lower())
                    discovered.append(file_obj)
                continue

            # Recursive directory walk
            try:
                for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
                    norm_dir = canonicalize_path(dirpath)
                    
                    # Filter out excluded subdirectories in-place so os.walk does not descend into them
                    dirnames[:] = [
                        d for d in dirnames
                        if not self._is_path_excluded(canonicalize_path(os.path.join(norm_dir, d)))
                    ]

                    for filename in filenames:
                        file_path = os.path.join(norm_dir, filename)
                        norm_file = canonicalize_path(file_path)

                        if self._is_path_excluded(norm_file):
                            continue

                        norm_file_key = norm_file.lower()
                        if norm_file_key in seen_files:
                            continue

                        file_obj = self._process_file(norm_file, root)
                        if file_obj:
                            seen_files.add(norm_file_key)
                            discovered.append(file_obj)

            except Exception as e:
                self.logger.warning(f"Error scanning directory '{root}': {e}")

        self.logger.info(f"Scan completed: Discovered {len(discovered)} files across {len(self.include_paths)} roots.")
        return discovered

    def _process_file(self, full_path: str, base_root: str) -> Optional[DiscoveredFile]:
        """Inspect a file and collect metadata safely."""
        try:
            # Check for symlink / reparse point
            if os.path.islink(full_path):
                self.logger.debug(f"Skipping symlink: '{full_path}'")
                return None

            st = os.stat(full_path)
            # Compute safe relative path
            try:
                rel_path = os.path.relpath(full_path, base_root)
            except ValueError:
                # Different drives on Windows
                rel_path = os.path.basename(full_path)

            file_name = os.path.basename(full_path)
            created_time = getattr(st, "st_ctime", None)

            return DiscoveredFile(
                original_path=full_path,
                relative_path=rel_path,
                file_name=file_name,
                size_bytes=st.st_size,
                modified_time=st.st_mtime,
                created_time=created_time,
                is_accessible=True,
                error_message=None
            )
        except (PermissionError, OSError) as e:
            self.logger.warning(f"File inaccessible during scan: '{full_path}': {e}")
            return DiscoveredFile(
                original_path=full_path,
                relative_path=os.path.basename(full_path),
                file_name=os.path.basename(full_path),
                size_bytes=0,
                modified_time=0.0,
                is_accessible=False,
                error_message=str(e)
            )
