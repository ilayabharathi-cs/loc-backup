"""Automated Windows-specific VSS & Locked-File Consistency Test Suite.

Verifies:
1. VSS availability detection
2. Administrative privilege detection
3. Real snapshot creation handling
4. Real snapshot path retrieval
5. Snapshot source-path mapping
6. Reading file from snapshot
7. Snapshot cleanup and emergency exit handler
8. Multiple sequential snapshot lifecycle
9. Snapshot creation failure handling
10. VSS service unavailable handling
11. Non-elevated execution classification
12. Backup with actively changing file (CHANGED_DURING_BACKUP detection)
13. Backup with locked file
14. Backup fallback when VSS is unavailable
15. Zero fake shadow-copy path generation invariant
"""

import os
import sys
import ctypes
import time
import pytest
import tempfile
import hashlib
from unittest.mock import MagicMock, patch

from agent.src.windows.vss import WindowsVSSProvider, LiveFilesystemProvider, get_vss_provider
from agent.src.windows.locked_files import LockedFileHandler, FileLockState, FileInspectionResult
from agent.src.windows.usn_journal import USNJournalProvider


def is_running_as_admin() -> bool:
    if sys.platform != "win32":
        return False
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def test_01_vss_availability_detection():
    """Test VSS availability detection matches actual OS and privileges."""
    provider = WindowsVSSProvider()
    avail, reason = provider.check_availability()
    if sys.platform != "win32":
        assert not avail
        assert "Windows" in reason
    else:
        admin = is_running_as_admin()
        if not admin:
            assert not avail
            assert "Administrator" in reason
        else:
            assert avail or "VSS" in reason


def test_02_administrative_privilege_detection():
    """Verify privilege detection logic."""
    provider = WindowsVSSProvider()
    if sys.platform == "win32":
        expected_admin = (ctypes.windll.shell32.IsUserAnAdmin() != 0)
        assert (provider.is_available() == expected_admin) or (not expected_admin and not provider.is_available())
    else:
        assert not provider.is_available()


def test_03_real_or_simulated_snapshot_creation():
    """Verify snapshot creation returns None when un-elevated and valid device path when elevated."""
    provider = WindowsVSSProvider()
    if not is_running_as_admin():
        # When not running as Administrator, create_snapshot must return None and not raise or fabricate paths
        snap = provider.create_snapshot("C:")
        assert snap is None, "create_snapshot must return None when running un-elevated"
    else:
        snap = provider.create_snapshot("C:")
        if snap:
            assert snap.startswith("\\\\?\\GLOBALROOT\\Device\\HarddiskVolumeShadowCopy")
            provider.release_snapshot("C:")


def test_04_snapshot_path_retrieval_and_mapping():
    """Verify source-to-snapshot path translation."""
    provider = WindowsVSSProvider()
    # Inject active snapshot mapping
    provider._active_snapshots["C:"] = "\\\\?\\GLOBALROOT\\Device\\HarddiskVolumeShadowCopy99"

    mapped = provider.get_snapshot_path("C:", "Users\\Administrator\\Documents\\test.txt")
    assert mapped == "\\\\?\\GLOBALROOT\\Device\\HarddiskVolumeShadowCopy99\\Users\\Administrator\\Documents\\test.txt"

    # Fallback to direct path when volume has no active snapshot
    fallback_mapped = provider.get_snapshot_path("D:", "Data\\file.csv")
    assert fallback_mapped == os.path.join("D:", "Data\\file.csv")


def test_05_snapshot_source_path_mapping_strips_leading_slashes():
    """Verify mapping handles leading forward and backslashes properly."""
    provider = WindowsVSSProvider()
    provider._active_snapshots["C:"] = "\\\\?\\GLOBALROOT\\Device\\HarddiskVolumeShadowCopy1"

    p1 = provider.get_snapshot_path("C:", "/logs/agent.log")
    p2 = provider.get_snapshot_path("C:", "\\logs\\agent.log")
    assert p1 == "\\\\?\\GLOBALROOT\\Device\\HarddiskVolumeShadowCopy1\\logs/agent.log" or p1 == "\\\\?\\GLOBALROOT\\Device\\HarddiskVolumeShadowCopy1\\logs\\agent.log"
    assert "\\logs" in p2


def test_06_reading_file_from_live_and_snapshot():
    """Verify file read from live file system and locked file handler."""
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(b"SAMPLE DATA FOR VSS READ TEST\n")
        tf_path = tf.name

    try:
        handler = LockedFileHandler(vss_provider=WindowsVSSProvider())
        inspection = handler.inspect_file(tf_path)
        assert inspection.state == FileLockState.READABLE
        assert inspection.size_bytes == len(b"SAMPLE DATA FOR VSS READ TEST\n")
        assert inspection.effective_path == tf_path
        assert not inspection.is_vss_used
    finally:
        if os.path.exists(tf_path):
            os.remove(tf_path)


def test_07_snapshot_cleanup_and_emergency_handler():
    """Verify snapshot release removes internal tracked state cleanly."""
    provider = WindowsVSSProvider()
    provider._active_snapshots["C:"] = "\\\\?\\GLOBALROOT\\Device\\HarddiskVolumeShadowCopy1"
    provider._active_snapshot_ids["C:"] = "{11111111-2222-3333-4444-555555555555}"

    provider.release_snapshot("C:")
    assert "C:" not in provider._active_snapshots
    assert "C:" not in provider._active_snapshot_ids


def test_08_multiple_sequential_snapshots():
    """Verify sequential creation and release of volume snapshots."""
    provider = WindowsVSSProvider()
    provider._active_snapshots["C:"] = "\\\\?\\GLOBALROOT\\Device\\HarddiskVolumeShadowCopy1"
    provider._active_snapshots["D:"] = "\\\\?\\GLOBALROOT\\Device\\HarddiskVolumeShadowCopy2"

    provider.release_snapshot()
    assert len(provider._active_snapshots) == 0
    assert len(provider._active_snapshot_ids) == 0


def test_09_snapshot_creation_failure_handling():
    """Verify non-zero command execution gracefully returns None with error logging."""
    provider = WindowsVSSProvider()
    with patch.object(provider, "check_availability", return_value=(True, "Simulated Admin")):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Access is denied or VSS disabled")
            res = provider.create_snapshot("C:")
            assert res is None


def test_10_vss_service_unavailable_handling():
    """Verify clean fallback when VSS service fails query."""
    provider = WindowsVSSProvider()
    with patch("ctypes.windll.shell32.IsUserAnAdmin", return_value=1):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1060, stdout="", stderr="The specified service does not exist as an installed service.")
            avail, reason = provider.check_availability()
            assert not avail
            assert "failed" in reason


def test_11_non_elevated_execution_classification():
    """Verify un-elevated execution clearly reports administrator requirement."""
    provider = WindowsVSSProvider()
    with patch("ctypes.windll.shell32.IsUserAnAdmin", return_value=0):
        avail, reason = provider.check_availability()
        assert not avail
        assert "Administrator" in reason


def test_12_backup_with_actively_changing_file():
    """Verify CHANGED_DURING_BACKUP detection when file mutates mid-operation."""
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(b"INITIAL CONTENT 12345")
        tf_path = tf.name

    try:
        handler = LockedFileHandler()
        inspection = handler.inspect_file(tf_path)
        assert inspection.state == FileLockState.READABLE

        # Mutate the file
        with open(tf_path, "wb") as f:
            f.write(b"MUTATED CONTENT EXTENDED 9999999999")

        # Consistency verification must detect change
        is_consistent = handler.verify_consistency_after_read(tf_path, inspection.size_bytes, inspection.modified_time)
        assert not is_consistent, "Consistency check must catch file size/mtime change"
    finally:
        if os.path.exists(tf_path):
            os.remove(tf_path)


def test_13_backup_with_locked_file():
    """Verify locked file inspection handles PermissionError cleanly without crashing."""
    handler = LockedFileHandler()
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(b"LOCKED DATA")
        tf_path = tf.name

    try:
        # Simulate exclusive open
        with patch("builtins.open", side_effect=PermissionError("The process cannot access the file because it is being used by another process.")):
            inspection = handler.inspect_file(tf_path)
            assert inspection.state == FileLockState.LOCKED
            assert "used by another process" in inspection.error_message
    finally:
        if os.path.exists(tf_path):
            os.remove(tf_path)


def test_14_backup_fallback_when_vss_unavailable():
    """Verify LiveFilesystemProvider functions seamlessly as fallback."""
    provider = get_vss_provider("LIVE")
    assert isinstance(provider, LiveFilesystemProvider)
    assert provider.is_available()
    assert provider.create_snapshot("C:") is None
    mapped = provider.get_snapshot_path("C:", "data\\test.txt")
    assert mapped == os.path.join("C:", "data\\test.txt")


def test_15_no_fake_shadow_copy_path_generation_invariant():
    """
    CRITICAL INVARIANT:
    The VSS provider must NEVER invent fake shadow copy paths like HarddiskVolumeShadowCopy_{pid}.
    If snapshot creation does not return a genuine VSS path from Windows, it MUST return None.
    """
    provider = WindowsVSSProvider()
    with patch.object(provider, "check_availability", return_value=(False, "Non-admin")):
        snap = provider.create_snapshot("C:")
        assert snap is None

    # Inspect source code of vss.py to ensure zero fake HarddiskVolumeShadowCopy_{os.getpid()} strings exist
    import inspect
    source = inspect.getsource(WindowsVSSProvider)
    assert "os.getpid()" not in source, "Source must not contain pid-based fake shadow copy generators!"
    assert "{os.getpid()}" not in source
