"""Metadata Restoration Handler for Windows Agent."""

import os
import sys
import datetime
from typing import Optional, List, Dict, Any


class MetadataWriter:
    """Applies timestamps and file attributes safely without corrupting restored content."""

    @staticmethod
    def apply_metadata(
        target_path: str,
        metadata_mode: str,
        modified_time: Optional[datetime.datetime] = None,
        access_time: Optional[datetime.datetime] = None,
        attributes: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        Applies metadata to a restored file based on metadata_mode (NONE, BASIC, FULL).
        Returns a list of non-fatal warnings encountered.
        """
        warnings: List[str] = []
        mode = (metadata_mode or "BASIC").upper()

        if mode == "NONE" or not os.path.exists(target_path):
            return warnings

        # 1. Timestamps (BASIC and FULL)
        if modified_time:
            try:
                mtime_epoch = modified_time.timestamp()
                atime_epoch = access_time.timestamp() if access_time else mtime_epoch
                os.utime(target_path, (atime_epoch, mtime_epoch))
            except Exception as e:
                warnings.append(f"Failed to set timestamps on '{target_path}': {e}")

        # 2. Windows Attributes (FULL)
        if mode == "FULL" and attributes and sys.platform == "win32":
            try:
                import ctypes
                FILE_ATTRIBUTE_READONLY = 0x1
                FILE_ATTRIBUTE_HIDDEN = 0x2
                FILE_ATTRIBUTE_ARCHIVE = 0x20

                flags = 0
                if attributes.get("readonly"):
                    flags |= FILE_ATTRIBUTE_READONLY
                if attributes.get("hidden"):
                    flags |= FILE_ATTRIBUTE_HIDDEN
                if attributes.get("archive"):
                    flags |= FILE_ATTRIBUTE_ARCHIVE

                if flags > 0:
                    ret = ctypes.windll.kernel32.SetFileAttributesW(target_path, flags)
                    if not ret:
                        warnings.append(f"SetFileAttributesW failed on '{target_path}'")
            except Exception as e:
                warnings.append(f"Windows attribute restoration warning: {e}")

        return warnings
