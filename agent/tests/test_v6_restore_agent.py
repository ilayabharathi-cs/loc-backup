"""Agent Tests for RetroVault V6: Restore & Disaster Recovery Engine."""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import hashlib
import tempfile
import pytest
import datetime

from agent.src.restore.path_validator import AgentPathValidator, AgentPathSafetyError
from agent.src.restore.conflict_resolver import ConflictResolver, RestoreConflictError
from agent.src.restore.destination_writer import DestinationWriter, ChecksumMismatchError
from agent.src.restore.metadata_writer import MetadataWriter
from agent.src.restore.restore_client import AgentRestoreClient


def test_agent_path_validator_safety():
    """Verify agent path safety rejects traversal and Windows reserved names."""
    with tempfile.TemporaryDirectory() as root:
        # Valid path
        valid_dest = AgentPathValidator.resolve_destination(root, "Documents\\report.docx")
        assert valid_dest.startswith(os.path.abspath(root))

        # Traversal attempt
        with pytest.raises(AgentPathSafetyError):
            AgentPathValidator.resolve_destination(root, "../../Windows/System32/evil.dll")

        # Reserved Windows device names
        with pytest.raises(AgentPathSafetyError):
            AgentPathValidator.resolve_destination(root, "CON")

        with pytest.raises(AgentPathSafetyError):
            AgentPathValidator.resolve_destination(root, "NUL.txt")

        with pytest.raises(AgentPathSafetyError):
            AgentPathValidator.resolve_destination(root, "Folder\\AUX\\file.txt")


def test_conflict_resolver_policies():
    """Verify ConflictResolver handles SKIP, OVERWRITE, RENAME, and FAIL."""
    with tempfile.TemporaryDirectory() as temp_dir:
        test_file = os.path.join(temp_dir, "document.txt")
        with open(test_file, "w") as f:
            f.write("existing")

        # 1. SKIP
        action, path = ConflictResolver.resolve_target(test_file, "SKIP")
        assert action == "SKIP"
        assert path == test_file

        # 2. OVERWRITE
        action, path = ConflictResolver.resolve_target(test_file, "OVERWRITE")
        assert action == "WRITE"
        assert path == test_file

        # 3. RENAME
        action, path = ConflictResolver.resolve_target(test_file, "RENAME")
        assert action == "WRITE"
        assert "document (Restored).txt" in path

        # 4. FAIL
        with pytest.raises(RestoreConflictError):
            ConflictResolver.resolve_target(test_file, "FAIL")


def test_destination_writer_atomic_success():
    """Verify DestinationWriter writes stream atomically and verifies SHA-256."""
    with tempfile.TemporaryDirectory() as dest_root:
        content = b"RetroVault V6 Production Agent Streamed Content Chunk\n" * 50
        content_sha = hashlib.sha256(content).hexdigest()

        # Stream in 100-byte chunks
        chunks = [content[i:i + 100] for i in range(0, len(content), 100)]

        res = DestinationWriter.write_stream_atomic(
            destination_root=dest_root,
            relative_path="Projects\\output.txt",
            stream_chunks=iter(chunks),
            expected_sha256=content_sha,
            conflict_mode="OVERWRITE"
        )

        assert res["success"] is True
        assert res["sha256"] == content_sha
        assert res["bytes_written"] == len(content)

        final_path = os.path.join(dest_root, "Projects", "output.txt")
        assert os.path.exists(final_path)
        with open(final_path, "rb") as f:
            assert f.read() == content


def test_destination_writer_checksum_mismatch_safety():
    """Verify that on checksum mismatch, the existing file is NOT modified and temp file is cleaned."""
    with tempfile.TemporaryDirectory() as dest_root:
        target_file = os.path.join(dest_root, "secure.dat")
        original_bytes = b"PRE_EXISTING_SECURE_DATA_DO_NOT_CORRUPT"
        with open(target_file, "wb") as f:
            f.write(original_bytes)

        corrupted_content = b"ATTACKER_CORRUPTED_STREAM"
        wrong_expected_sha = hashlib.sha256(b"SOMETHING_ELSE").hexdigest()

        with pytest.raises(ChecksumMismatchError):
            DestinationWriter.write_stream_atomic(
                destination_root=dest_root,
                relative_path="secure.dat",
                stream_chunks=iter([corrupted_content]),
                expected_sha256=wrong_expected_sha,
                conflict_mode="OVERWRITE"
            )

        # Ensure original file is completely intact
        with open(target_file, "rb") as f:
            assert f.read() == original_bytes

        # Ensure no temporary file leaked in directory
        files_in_dir = os.listdir(dest_root)
        assert len(files_in_dir) == 1
        assert files_in_dir[0] == "secure.dat"


def test_metadata_writer():
    """Verify MetadataWriter sets timestamps on restored files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        test_file = os.path.join(temp_dir, "meta.txt")
        with open(test_file, "w") as f:
            f.write("test")

        past_time = datetime.datetime(2025, 5, 10, 12, 0, 0, tzinfo=datetime.timezone.utc)
        warnings = MetadataWriter.apply_metadata(
            target_path=test_file,
            metadata_mode="BASIC",
            modified_time=past_time
        )
        assert len(warnings) == 0
        file_mtime = os.path.getmtime(test_file)
        assert int(file_mtime) == int(past_time.timestamp())


def test_agent_restore_client_command_dispatch():
    """Verify agent restore command protocol (start, pause, resume, cancel)."""
    client = AgentRestoreClient(api_key="SECRET_V6_KEY")

    # Unauthorized request
    unauth = client.handle_command("start", "RESTORE-1", auth_token="WRONG_KEY")
    assert unauth["success"] is False
    assert unauth["error"] == "UNAUTHORIZED"

    # Authorized start
    start_res = client.handle_command("start", "RESTORE-1", auth_token="SECRET_V6_KEY")
    assert start_res["success"] is True
    assert start_res["status"] == "RUNNING"

    # Pause
    pause_res = client.handle_command("pause", "RESTORE-1", auth_token="SECRET_V6_KEY")
    assert pause_res["success"] is True
    assert pause_res["status"] == "PAUSED"

    # Resume
    resume_res = client.handle_command("resume", "RESTORE-1", auth_token="SECRET_V6_KEY")
    assert resume_res["success"] is True
    assert resume_res["status"] == "RESUMING"

    # Cancel
    cancel_res = client.handle_command("cancel", "RESTORE-1", auth_token="SECRET_V6_KEY")
    assert cancel_res["success"] is True
    assert cancel_res["status"] == "CANCELLED"
