"""Windows NTFS USN Change Journal integration for RetroVault Agent V4/V5.

IMPORTANT ARCHITECTURAL RULE (PHASE 6):
USN Journal is strictly an OPTIMIZATION to discover candidate changed paths.
It NEVER replaces V3 metadata verification (size + mtime + hash) as the ground truth.
All candidate paths returned by this provider MUST be validated against the active filesystem.
If USN Journal is unavailable or access is restricted, the engine falls back seamlessly
to recursive directory metadata scanning.
"""

import os
import sys
import ctypes
from typing import Optional, Set, List, Tuple
from agent.src.logger import get_logger
from agent.native.python.native_bridge import get_native_bridge


class USNJournalProvider:
    """
    Interfaces with Windows NTFS Update Sequence Number (USN) Change Journal.
    Yields candidate modified/created paths to accelerate change detection.
    Backed by high-performance native Win32 C/C++ DeviceIoControl layer.
    """

    def __init__(self):
        self.logger = get_logger()

    def is_available(self, volume: str) -> bool:
        """Check if target volume is NTFS and USN Journal can be queried."""
        if sys.platform != "win32":
            return False

        bridge = get_native_bridge()
        if bridge.is_available:
            avail, reason = bridge.usn_check_availability(volume)
            if not avail:
                self.logger.debug(f"Native USN check for '{volume}': {reason}")
            return avail

        # Python fallback check
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
            if not is_admin:
                self.logger.debug("USN Journal optimization unavailable: Non-admin process.")
                return False

            norm_vol = volume.rstrip("\\")
            if not norm_vol.endswith(":"):
                norm_vol = f"{norm_vol}:"
            root_path = f"{norm_vol}\\"

            fs_name_buf = ctypes.create_unicode_buffer(32)
            res = ctypes.windll.kernel32.GetVolumeInformationW(
                root_path,
                None, 0, None, None, None,
                fs_name_buf, len(fs_name_buf)
            )
            return bool(res and fs_name_buf.value == "NTFS")
        except Exception as e:
            self.logger.debug(f"USN availability check fallback failed for '{volume}': {e}")
            return False

    def get_journal_info(self, volume: str) -> Tuple[Optional[int], Optional[int]]:
        """Query journal ID and next USN."""
        bridge = get_native_bridge()
        if bridge.is_available and self.is_available(volume):
            return bridge.usn_query_info(volume)
        return None, None

    def query_candidate_changed_files(
        self,
        volume: str,
        since_usn: Optional[int] = None
    ) -> Optional[Set[str]]:
        """
        Query NTFS USN Change Journal for files modified or created since previous USN checkpoint.
        Returns a set of candidate relative file names/paths, or None if USN Journal query is unavailable/failed.

        NOTE: If None is returned, callers must seamlessly fall back to standard metadata directory scanning.
        """
        if not self.is_available(volume):
            self.logger.info(f"USN Journal query unavailable for '{volume}'; falling back to metadata directory scan.")
            return None

        bridge = get_native_bridge()
        if not bridge.is_available:
            self.logger.info(f"Native USN bridge unavailable for '{volume}'; falling back to metadata directory scan.")
            return None

        try:
            start_usn = since_usn if since_usn is not None else 0
            self.logger.info(f"Querying native NTFS USN Change Journal on volume '{volume}' since USN={start_usn}...")
            
            records, highest_usn = bridge.usn_read_changes(volume, start_usn)
            
            candidates: Set[str] = set()
            for f_ref, p_ref, rec_usn, reason, name in records:
                if name:
                    candidates.add(name.lower())

            self.logger.info(
                f"USN query completed on '{volume}': retrieved {len(records)} records, "
                f"{len(candidates)} unique candidates, highest USN={highest_usn}."
            )
            return candidates
        except Exception as e:
            self.logger.warning(f"Error querying USN Journal on '{volume}': {e}. Falling back to metadata scan.")
            return None
