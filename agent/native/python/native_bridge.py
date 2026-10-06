"""RetroVault Native C/C++ Bridge.
Safe, robust Python interface to high-performance Windows native operations.

Features:
- Safe DLL discovery from controlled application directory (Phase 18 Security)
- Automatic fallback detection (Phase 13 Fallback)
- Exception containment: native errors never crash Python
- Clean Python data structures (DiscoveredFile, tuples, clean primitives)
"""

import os
import sys
import ctypes
import logging
from typing import List, Set, Optional, Tuple, Callable
from agent.src.backup.models import DiscoveredFile
from agent.src.utils.filesystem import canonicalize_path
from agent.src.logger import get_logger

logger = get_logger()

# Constants matching native headers
RV_MAX_PATH = 1024
RV_BATCH_SIZE = 512

# File IO Results
RV_IO_SUCCESS = 0
RV_IO_LOCKED = 1
RV_IO_ACCESS_DENIED = 2
RV_IO_NOT_FOUND = 3
RV_IO_READ_ERROR = 4
RV_IO_MODIFIED_DURING_READ = 5

# USN Results
RV_USN_OK = 0
RV_USN_NOT_ADMIN = 1
RV_USN_NOT_NTFS = 2
RV_USN_JOURNAL_NOT_ACTIVE = 3
RV_USN_ACCESS_DENIED = 4
RV_USN_JOURNAL_TRUNCATED = 5
RV_USN_ERROR = 6

# VSS Results
RV_VSS_OK = 0
RV_VSS_NOT_ADMIN = 1
RV_VSS_SERVICE_UNAVAILABLE = 2
RV_VSS_TIMEOUT = 3
RV_VSS_FAILED = 4


class RVFileInfo(ctypes.Structure):
    _fields_ = [
        ("path", ctypes.c_wchar * RV_MAX_PATH),
        ("size_bytes", ctypes.c_uint64),
        ("modified_time", ctypes.c_double),
        ("created_time", ctypes.c_double),
        ("attributes", ctypes.c_uint32),
        ("is_directory", ctypes.c_uint32),
    ]


class RVFileStat(ctypes.Structure):
    _fields_ = [
        ("status", ctypes.c_int),
        ("size_bytes", ctypes.c_uint64),
        ("modified_time", ctypes.c_double),
        ("created_time", ctypes.c_double),
        ("attributes", ctypes.c_uint32),
        ("win32_error_code", ctypes.c_uint32),
    ]


RVScanCallbackType = ctypes.CFUNCTYPE(
    None,
    ctypes.POINTER(RVFileInfo),
    ctypes.c_int,
    ctypes.c_void_p
)

RVUSNRecordCallbackType = ctypes.CFUNCTYPE(
    None,
    ctypes.c_uint64,  # file_ref_number
    ctypes.c_uint64,  # parent_ref_number
    ctypes.c_uint64,  # usn
    ctypes.c_uint32,  # reason
    ctypes.c_wchar_p,  # file_name
    ctypes.c_void_p   # user_data
)


class NativeBridge:
    """Manages the lifetime and bindings of retrovault_native.dll."""

    _instance: Optional["NativeBridge"] = None

    def __init__(self):
        self._dll: Optional[ctypes.CDLL] = None
        self._available = False
        self._init_error: Optional[str] = None
        self._load_dll()

    @classmethod
    def get_instance(cls) -> "NativeBridge":
        if cls._instance is None:
            cls._instance = NativeBridge()
        return cls._instance

    @property
    def is_available(self) -> bool:
        return self._available and self._dll is not None

    @property
    def init_error(self) -> Optional[str]:
        return self._init_error

    def _load_dll(self) -> None:
        """Locates and loads retrovault_native.dll strictly from trusted local directory."""
        if sys.platform != "win32":
            self._init_error = f"Platform {sys.platform} not supported for native Windows module."
            self._available = False
            return

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidate_paths = [
            os.path.join(base_dir, "bin", "retrovault_native.dll"),
            os.path.join(base_dir, "bin", "libretrovault_native.dll"),
            os.path.join(base_dir, "build", "retrovault_native.dll"),
        ]

        dll_path = None
        for p in candidate_paths:
            if os.path.exists(p):
                dll_path = p
                break

        if not dll_path:
            self._init_error = f"retrovault_native.dll not found in candidate paths: {candidate_paths}"
            logger.info(f"Native module unavailable: {self._init_error}. Using pure Python fallback.")
            self._available = False
            return

        try:
            # Win32 security: load from specific absolute directory only
            dll_dir = os.path.dirname(dll_path)
            if hasattr(os, "add_dll_directory"):
                os.add_dll_directory(dll_dir)

            self._dll = ctypes.CDLL(dll_path)
            self._bind_functions()
            self._available = True
            logger.info(f"RetroVault Native C/C++ engine loaded successfully from '{dll_path}'.")
        except Exception as e:
            self._init_error = str(e)
            logger.warning(f"Failed to load native library '{dll_path}': {e}. Falling back to Python.")
            self._dll = None
            self._available = False

    def _bind_functions(self) -> None:
        """Bind and configure function signatures."""
        assert self._dll is not None

        # rv_scan_directory
        self._dll.rv_scan_directory.argtypes = [
            ctypes.POINTER(ctypes.c_wchar_p),  # roots
            ctypes.c_int,                      # root_count
            ctypes.POINTER(ctypes.c_wchar_p),  # excludes
            ctypes.c_int,                      # exclude_count
            RVScanCallbackType,                # callback
            ctypes.c_void_p,                   # user_data
            ctypes.POINTER(ctypes.c_int)       # cancel_flag
        ]
        self._dll.rv_scan_directory.restype = ctypes.c_int

        # rv_file_inspect
        self._dll.rv_file_inspect.argtypes = [
            ctypes.c_wchar_p,                  # path
            ctypes.POINTER(RVFileStat)         # out_stat
        ]
        self._dll.rv_file_inspect.restype = ctypes.c_int

        # rv_file_read_chunk
        self._dll.rv_file_read_chunk.argtypes = [
            ctypes.c_wchar_p,                  # path
            ctypes.c_uint64,                   # offset
            ctypes.POINTER(ctypes.c_uint8),    # buffer
            ctypes.c_uint32,                   # buffer_len
            ctypes.POINTER(ctypes.c_uint32)    # bytes_read
        ]
        self._dll.rv_file_read_chunk.restype = ctypes.c_int

        # rv_file_verify_consistency
        self._dll.rv_file_verify_consistency.argtypes = [
            ctypes.c_wchar_p,                  # path
            ctypes.c_uint64,                   # expected_size
            ctypes.c_double                    # expected_mtime
        ]
        self._dll.rv_file_verify_consistency.restype = ctypes.c_int

        # rv_usn_check_availability
        self._dll.rv_usn_check_availability.argtypes = [
            ctypes.c_wchar_p,                  # volume_path
            ctypes.c_wchar_p,                  # out_reason
            ctypes.c_int                       # max_reason_len
        ]
        self._dll.rv_usn_check_availability.restype = ctypes.c_int

        # rv_usn_query_info
        self._dll.rv_usn_query_info.argtypes = [
            ctypes.c_wchar_p,                  # volume_path
            ctypes.POINTER(ctypes.c_uint64),   # out_journal_id
            ctypes.POINTER(ctypes.c_uint64)    # out_next_usn
        ]
        self._dll.rv_usn_query_info.restype = ctypes.c_int

        # rv_usn_read_changes
        self._dll.rv_usn_read_changes.argtypes = [
            ctypes.c_wchar_p,                  # volume_path
            ctypes.c_uint64,                   # since_usn
            RVUSNRecordCallbackType,           # callback
            ctypes.c_void_p,                   # user_data
            ctypes.POINTER(ctypes.c_uint64)    # out_highest_usn
        ]
        self._dll.rv_usn_read_changes.restype = ctypes.c_int

        # rv_vss_is_admin
        self._dll.rv_vss_is_admin.argtypes = []
        self._dll.rv_vss_is_admin.restype = ctypes.c_int

        # rv_vss_resolve_path
        self._dll.rv_vss_resolve_path.argtypes = [
            ctypes.c_wchar_p,                  # snapshot_device
            ctypes.c_wchar_p,                  # relative_path
            ctypes.c_wchar_p,                  # out_mapped_path
            ctypes.c_int                       # max_mapped_len
        ]
        self._dll.rv_vss_resolve_path.restype = ctypes.c_int

        # rv_vss_create_snapshot
        self._dll.rv_vss_create_snapshot.argtypes = [
            ctypes.c_wchar_p,                  # volume_letter
            ctypes.c_wchar_p,                  # out_device
            ctypes.c_int,                      # max_device_len
            ctypes.c_wchar_p,                  # out_id
            ctypes.c_int,                      # max_id_len
            ctypes.c_wchar_p,                  # out_error
            ctypes.c_int                       # max_error_len
        ]
        self._dll.rv_vss_create_snapshot.restype = ctypes.c_int

        # rv_vss_delete_snapshot
        self._dll.rv_vss_delete_snapshot.argtypes = [
            ctypes.c_wchar_p,                  # snapshot_id
            ctypes.c_wchar_p,                  # out_error
            ctypes.c_int                       # max_error_len
        ]
        self._dll.rv_vss_delete_snapshot.restype = ctypes.c_int

    def scan_directories(
        self,
        include_paths: List[str],
        exclude_paths: Optional[List[str]] = None,
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> List[DiscoveredFile]:
        """
        Recursively discovers eligible backup files using native Windows FindFirstFileExW.
        Returns DiscoveredFile objects exactly matching Python FileScanner schema.
        """
        if not self.is_available:
            raise RuntimeError("Native module is not available.")

        norm_includes = [canonicalize_path(p) for p in include_paths if p]
        norm_excludes = [canonicalize_path(p).lower() for p in (exclude_paths or []) if p]

        discovered: List[DiscoveredFile] = []
        seen_keys: Set[str] = set()

        # Build base mapping for relative path calculation
        # Map each include root
        roots_arr = (ctypes.c_wchar_p * len(norm_includes))(*norm_includes)
        excludes_arr = (ctypes.c_wchar_p * len(norm_excludes))(*norm_excludes)

        cancel_val = ctypes.c_int(0)

        def on_batch(items_ptr, count, user_data):
            for i in range(count):
                if cancel_check and cancel_check():
                    cancel_val.value = 1
                    return

                item = items_ptr[i]
                if item.is_directory:
                    continue

                full_path = item.path
                key = full_path.lower()
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                # Compute relative path against appropriate root
                rel_path = os.path.basename(full_path)
                for root in norm_includes:
                    if full_path.lower().startswith(root.lower()):
                        try:
                            rel_path = os.path.relpath(full_path, root)
                        except ValueError:
                            rel_path = os.path.basename(full_path)
                        break

                f_obj = DiscoveredFile(
                    original_path=full_path,
                    relative_path=rel_path,
                    file_name=os.path.basename(full_path),
                    size_bytes=int(item.size_bytes),
                    modified_time=float(item.modified_time),
                    created_time=float(item.created_time) if item.created_time > 0 else None,
                    is_accessible=True,
                    error_message=None
                )
                discovered.append(f_obj)

        cb = RVScanCallbackType(on_batch)

        rc = self._dll.rv_scan_directory(
            roots_arr,
            len(norm_includes),
            excludes_arr,
            len(norm_excludes),
            cb,
            None,
            ctypes.byref(cancel_val)
        )

        if rc != 0:
            raise RuntimeError(f"Native scan failed with return code {rc}")

        return discovered

    def inspect_file(self, path: str) -> RVFileStat:
        """Inspect file accessibility, locks, and attributes using native Win32 API."""
        if not self.is_available:
            raise RuntimeError("Native module is not available.")

        stat = RVFileStat()
        res = self._dll.rv_file_inspect(path, ctypes.byref(stat))
        return stat

    def read_file_chunk(self, path: str, offset: int, length: int) -> bytes:
        """Stream a bounded slice of file bytes using native Win32 CreateFileW."""
        if not self.is_available:
            raise RuntimeError("Native module is not available.")

        buf = (ctypes.c_uint8 * length)()
        bytes_read = ctypes.c_uint32(0)

        res = self._dll.rv_file_read_chunk(
            path,
            ctypes.c_uint64(offset),
            buf,
            ctypes.c_uint32(length),
            ctypes.byref(bytes_read)
        )

        if res != RV_IO_SUCCESS:
            raise OSError(res, f"Native read chunk failed with code {res}")

        actual_len = bytes_read.value
        return bytes(buf[:actual_len])

    def verify_consistency(self, path: str, expected_size: int, expected_mtime: float) -> bool:
        """Verifies if file size and mtime remained unchanged."""
        if not self.is_available:
            raise RuntimeError("Native module is not available.")

        res = self._dll.rv_file_verify_consistency(
            path,
            ctypes.c_uint64(expected_size),
            ctypes.c_double(expected_mtime)
        )
        return res == 1

    def usn_check_availability(self, volume: str) -> Tuple[bool, str]:
        """Check if target volume has active NTFS USN Journal and admin privileges."""
        if not self.is_available:
            return False, "Native module unavailable"

        reason_buf = ctypes.create_unicode_buffer(512)
        res = self._dll.rv_usn_check_availability(volume, reason_buf, 512)
        return (res == RV_USN_OK, reason_buf.value)

    def usn_query_info(self, volume: str) -> Tuple[Optional[int], Optional[int]]:
        """Query current USN Journal ID and Next USN."""
        if not self.is_available:
            return None, None

        jid = ctypes.c_uint64(0)
        next_usn = ctypes.c_uint64(0)
        res = self._dll.rv_usn_query_info(volume, ctypes.byref(jid), ctypes.byref(next_usn))
        if res == RV_USN_OK:
            return jid.value, next_usn.value
        return None, None

    def usn_read_changes(
        self,
        volume: str,
        since_usn: int
    ) -> Tuple[List[Tuple[int, int, int, int, str]], int]:
        """Read changes from NTFS USN Journal since given checkpoint."""
        if not self.is_available:
            return [], since_usn

        records = []

        def on_record(f_ref, p_ref, usn_val, reason_val, name_val, user_data):
            records.append((f_ref, p_ref, usn_val, reason_val, name_val))

        cb = RVUSNRecordCallbackType(on_record)
        highest_usn = ctypes.c_uint64(since_usn)

        res = self._dll.rv_usn_read_changes(
            volume,
            ctypes.c_uint64(since_usn),
            cb,
            None,
            ctypes.byref(highest_usn)
        )

        if res != RV_USN_OK:
            logger.warning(f"Native USN read returned code {res}")

        return records, highest_usn.value

    def vss_is_admin(self) -> bool:
        """Check if elevated."""
        if not self.is_available:
            return False
        return self._dll.rv_vss_is_admin() != 0

    def vss_resolve_path(self, snapshot_device: str, relative_path: str) -> str:
        """Resolve path in shadow copy device."""
        if not self.is_available:
            return os.path.join(snapshot_device, relative_path)

        out_buf = ctypes.create_unicode_buffer(RV_MAX_PATH)
        rc = self._dll.rv_vss_resolve_path(snapshot_device, relative_path, out_buf, RV_MAX_PATH)
        if rc == 0 and out_buf.value:
            return out_buf.value
        return os.path.join(snapshot_device, relative_path)

    def vss_create_snapshot(self, volume: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Creates VSS snapshot. Returns (device_path, snapshot_id, error_message)."""
        if not self.is_available:
            return None, None, "Native VSS unavailable"

        dev_buf = ctypes.create_unicode_buffer(RV_MAX_PATH)
        id_buf = ctypes.create_unicode_buffer(128)
        err_buf = ctypes.create_unicode_buffer(1024)

        res = self._dll.rv_vss_create_snapshot(
            volume,
            dev_buf, RV_MAX_PATH,
            id_buf, 128,
            err_buf, 1024
        )

        if res == RV_VSS_OK and dev_buf.value:
            return dev_buf.value, id_buf.value, None
        return None, None, err_buf.value or f"VSS error code {res}"

    def vss_delete_snapshot(self, snapshot_id: str) -> Tuple[bool, Optional[str]]:
        """Deletes VSS snapshot."""
        if not self.is_available:
            return False, "Native VSS unavailable"

        err_buf = ctypes.create_unicode_buffer(1024)
        res = self._dll.rv_vss_delete_snapshot(snapshot_id, err_buf, 1024)
        if res == RV_VSS_OK:
            return True, None
        return False, err_buf.value or f"VSS delete error code {res}"


# Global convenience accessor
def get_native_bridge() -> NativeBridge:
    return NativeBridge.get_instance()
