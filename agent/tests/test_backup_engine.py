"""Automated test suite for RetroVault Backup Engine V2 (Agent-side)."""

import os
import sys
import tempfile
import pytest
from unittest.mock import MagicMock, patch

# Ensure agent imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from agent.src.config import AgentConfig
from agent.src.identity import DeviceIdentity
from agent.src.policy_resolver import ResolvedPolicy
from agent.src.backup.models import DiscoveredFile, FileUploadResult, BackupType
from agent.src.backup.hashing import calculate_file_sha256
from agent.src.backup.scanner import FileScanner
from agent.src.backup.uploader import FileUploader
from agent.src.backup.backup_engine import BackupEngine


# ==============================================================================
# 1. File Discovery & Recursive Scanning
# ==============================================================================
def test_file_discovery_and_recursive_scanning(tmp_path):
    """Verify recursive scanning discovers nested files and records metadata."""
    root = tmp_path / "Documents"
    root.mkdir()
    (root / "doc1.txt").write_text("Hello World", encoding="utf-8")
    sub = root / "SubFolder"
    sub.mkdir()
    (sub / "doc2.pdf").write_bytes(b"%PDF-1.4 test")

    scanner = FileScanner(include_paths=[str(root)])
    files = scanner.scan()

    file_names = {f.file_name for f in files}
    assert "doc1.txt" in file_names
    assert "doc2.pdf" in file_names
    assert len(files) == 2

    doc1 = next(f for f in files if f.file_name == "doc1.txt")
    assert doc1.size_bytes == 11
    assert doc1.is_accessible is True
    assert doc1.relative_path == "doc1.txt"


# ==============================================================================
# 2. Exclusion Rules
# ==============================================================================
def test_scanner_exclusion_rules(tmp_path):
    """Verify excluded paths and subdirectories are skipped."""
    root = tmp_path / "Data"
    root.mkdir()
    (root / "keep.txt").write_text("keep me", encoding="utf-8")
    skip_dir = root / "temp"
    skip_dir.mkdir()
    (skip_dir / "skip.tmp").write_text("temporary", encoding="utf-8")

    scanner = FileScanner(include_paths=[str(root)], exclude_paths=[str(skip_dir)])
    files = scanner.scan()

    assert len(files) == 1
    assert files[0].file_name == "keep.txt"


# ==============================================================================
# 3. SHA-256 Calculation & Large-File Streaming
# ==============================================================================
def test_streaming_sha256_calculation(tmp_path):
    """Verify incremental chunked SHA-256 calculation matches expected digest."""
    test_file = tmp_path / "sample.bin"
    # Create 1 MB pseudo-file
    data = b"RetroVault-Enterprise-Backup-1995" * 30000
    test_file.write_bytes(data)

    import hashlib
    expected_hash = hashlib.sha256(data).hexdigest()

    computed_hash, total_bytes = calculate_file_sha256(str(test_file), chunk_size=8192)
    assert computed_hash == expected_hash
    assert total_bytes == len(data)


# ==============================================================================
# 4. Inaccessible / Locked File Handling
# ==============================================================================
def test_locked_file_handling():
    """Verify locked file is caught safely without crashing the uploader."""
    config = AgentConfig()
    uploader = FileUploader(config, client_id="PC-001", run_id=1)

    file_info = DiscoveredFile(
        original_path="/non/existent/path/locked.docx",
        relative_path="locked.docx",
        file_name="locked.docx",
        size_bytes=100,
        modified_time=0.0,
        is_accessible=False,
        error_message="Access denied by another process"
    )

    result = uploader.upload_file(file_info)
    assert result.status == "locked"
    assert "Access denied" in (result.error_message or "")


# ==============================================================================
# 5. File Changed During Backup Detection
# ==============================================================================
def test_changed_during_backup_detection(tmp_path):
    """Verify file modification between pre-stat and upload is detected."""
    test_file = tmp_path / "active_doc.txt"
    test_file.write_text("Version 1", encoding="utf-8")

    config = AgentConfig()
    uploader = FileUploader(config, client_id="PC-001", run_id=1)

    file_info = DiscoveredFile(
        original_path=str(test_file),
        relative_path="active_doc.txt",
        file_name="active_doc.txt",
        size_bytes=9,
        modified_time=os.path.getmtime(str(test_file))
    )

    # Simulate file modifying during operation
    with patch("os.stat") as mock_stat:
        real_stat = os.stat(str(test_file))
        # First stat returns original, second stat returns modified mtime
        mock_stat.side_effect = [
            real_stat,
            MagicMock(st_size=real_stat.st_size, st_mtime=real_stat.st_mtime + 5.0)
        ]
        res = uploader.upload_file(file_info)
        assert res.status == "changed_during_backup"


# ==============================================================================
# 6. Upload Retry on Network Failure
# ==============================================================================
def test_uploader_retry_on_network_failure(tmp_path):
    """Verify exponential backoff retry when HTTP requests encounter network drops."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("data", encoding="utf-8")

    config = AgentConfig(server_url="http://mock-server:8000", max_retries=3, request_timeout_seconds=1)
    uploader = FileUploader(config, client_id="PC-001", run_id=1)

    file_info = DiscoveredFile(
        original_path=str(test_file),
        relative_path="test.txt",
        file_name="test.txt",
        size_bytes=4,
        modified_time=os.path.getmtime(str(test_file))
    )

    from urllib.error import URLError
    with patch("urllib.request.urlopen", side_effect=URLError("Connection refused")), patch("time.sleep"):
        res = uploader.upload_file(file_info)
        assert res.status == "failed"
        assert res.retries == 3


# ==============================================================================
# 7. Backup Engine Full Orchestration
# ==============================================================================
def test_backup_engine_orchestration(tmp_path):
    """Verify BackupEngine scans, initializes run, uploads files, and completes."""
    test_dir = tmp_path / "BackupSource"
    test_dir.mkdir()
    (test_dir / "file1.txt").write_text("content 1", encoding="utf-8")
    (test_dir / "file2.txt").write_text("content 2", encoding="utf-8")

    config = AgentConfig(server_url="http://mock-server:8000")
    identity = DeviceIdentity(str(tmp_path / "identity.json"))
    identity.set_registration("PC-001")

    api_mock = MagicMock()
    # Mock /backups/runs response
    api_mock._make_request.side_effect = [
        {"success": True, "data": {"id": 42}},  # POST /backups/runs
        {"success": True, "data": {}},           # POST /backups/runs/42/progress
        {"success": True, "data": {"status": "completed"}}  # POST /backups/runs/42/complete
    ]

    policy = ResolvedPolicy(
        policy_id=1,
        policy_name="Test Policy",
        valid_paths=[str(test_dir)],
        excluded_paths=[]
    )

    engine = BackupEngine(config, identity, api_mock)

    with patch.object(FileUploader, "upload_file") as mock_upload:
        mock_upload.side_effect = [
            FileUploadResult(file_name="file1.txt", original_path=str(test_dir / "file1.txt"), size_bytes=9, status="uploaded"),
            FileUploadResult(file_name="file2.txt", original_path=str(test_dir / "file2.txt"), size_bytes=9, status="uploaded")
        ]
        summary = engine.run_full_backup(policy)

        assert summary.run_id == 42
        assert summary.status == "completed"
        assert summary.files_discovered == 2
        assert summary.files_uploaded == 2
        assert summary.files_failed == 0
        assert summary.recovery_point_created is True
