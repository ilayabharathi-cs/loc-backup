"""Comprehensive Test Suite for RetroVault Native C/C++ Engine & Fallbacks."""

import os
import sys
import unittest
import tempfile
import shutil
import time

# Ensure import paths
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("agent"))

from agent.native.python.native_bridge import get_native_bridge, NativeBridge
from agent.src.backup.scanner import FileScanner
from agent.src.windows.locked_files import LockedFileHandler, FileLockState
from agent.src.windows.usn_journal import USNJournalProvider
from agent.src.windows.vss import WindowsVSSProvider, LiveFilesystemProvider


class TestHybridNativeEngine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_dir = tempfile.mkdtemp(prefix="rv_test_native_")
        
        # Create nested test files
        cls.file_a = os.path.join(cls.test_dir, "file_a.txt")
        with open(cls.file_a, "wb") as f:
            f.write(b"Hello RetroVault Native A")

        cls.sub_dir = os.path.join(cls.test_dir, "subdir")
        os.makedirs(cls.sub_dir, exist_ok=True)
        cls.file_b = os.path.join(cls.sub_dir, "file_b.bin")
        with open(cls.file_b, "wb") as f:
            f.write(b"Binary Data B" * 100)

        cls.exc_dir = os.path.join(cls.test_dir, "excluded_folder")
        os.makedirs(cls.exc_dir, exist_ok=True)
        cls.file_exc = os.path.join(cls.exc_dir, "should_not_see.txt")
        with open(cls.file_exc, "wb") as f:
            f.write(b"Excluded")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def test_01_native_bridge_availability(self):
        bridge = get_native_bridge()
        self.assertTrue(bridge.is_available, f"Bridge failed to load: {bridge.init_error}")

    def test_02_scanner_equivalence(self):
        # Native scan
        native_scanner = FileScanner(
            include_paths=[self.test_dir],
            exclude_paths=[self.exc_dir],
            use_native=True
        )
        native_files = native_scanner.scan()

        # Python fallback scan
        py_scanner = FileScanner(
            include_paths=[self.test_dir],
            exclude_paths=[self.exc_dir],
            use_native=False
        )
        py_files = py_scanner.scan()

        self.assertEqual(len(native_files), len(py_files))
        
        # Sort by relative path to compare
        native_map = {f.relative_path.replace("\\", "/").lower(): f for f in native_files}
        py_map = {f.relative_path.replace("\\", "/").lower(): f for f in py_files}

        self.assertEqual(set(native_map.keys()), set(py_map.keys()))

        for k in native_map:
            nf = native_map[k]
            pf = py_map[k]
            self.assertEqual(nf.size_bytes, pf.size_bytes)
            self.assertAlmostEqual(nf.modified_time, pf.modified_time, delta=1.0)
            self.assertEqual(nf.file_name, pf.file_name)

        # Excluded folder must not be present
        self.assertNotIn("excluded_folder/should_not_see.txt", native_map)

    def test_03_file_inspection_and_reading(self):
        bridge = get_native_bridge()
        stat = bridge.inspect_file(self.file_a)
        self.assertEqual(stat.status, 0)
        self.assertEqual(stat.size_bytes, os.path.getsize(self.file_a))

        # Test chunk reading
        chunk = bridge.read_file_chunk(self.file_a, 0, 5)
        self.assertEqual(chunk, b"Hello")

        # Test consistency verification
        self.assertTrue(bridge.verify_consistency(self.file_a, stat.size_bytes, stat.modified_time))
        self.assertFalse(bridge.verify_consistency(self.file_a, stat.size_bytes + 10, stat.modified_time))

    def test_04_locked_file_handler_with_native(self):
        handler = LockedFileHandler()
        res = handler.inspect_file(self.file_b, "subdir/file_b.bin")
        self.assertEqual(res.state, FileLockState.READABLE)
        self.assertEqual(res.size_bytes, os.path.getsize(self.file_b))

        # Test non-existent file
        res_non = handler.inspect_file(os.path.join(self.test_dir, "non_existent.xyz"))
        self.assertEqual(res_non.state, FileLockState.NOT_FOUND)

    def test_05_usn_provider_fallback_safety(self):
        usn = USNJournalProvider()
        # Non-admin or non-NTFS returns False safely without crash
        avail = usn.is_available("C:")
        self.assertIsInstance(avail, bool)

        # Query candidates should cleanly return set or None (which triggers fallback to metadata scan)
        candidates = usn.query_candidate_changed_files("C:", since_usn=0)
        self.assertTrue(candidates is None or isinstance(candidates, set))

    def test_06_vss_provider_safety(self):
        vss = WindowsVSSProvider()
        avail, reason = vss.check_availability()
        self.assertIsInstance(avail, bool)
        self.assertIsInstance(reason, str)

        # LiveFilesystemProvider remains available
        live = LiveFilesystemProvider()
        self.assertTrue(live.is_available())
        path = live.get_snapshot_path("C:", "test.txt")
        self.assertTrue(path.endswith("test.txt"))

    def test_07_resilience_on_invalid_native_call(self):
        bridge = get_native_bridge()
        # Invalid path inspection should not crash process
        stat = bridge.inspect_file(r"Z:\Totally\Invalid\Path\File.abc")
        self.assertNotEqual(stat.status, 0)


if __name__ == "__main__":
    unittest.main()
