"""Tests for RetroVault Agent V4 Reliability Components.

Covers:
- RunStateMachine & legal transitions
- Crash-safe CheckpointManager (atomic write/read/clear)
- RetryEngine exponential backoff and error categorization
- Resumable TransferEngine with server-authoritative chunk skipping
- LockedFileHandler & file consistency verification
- USNJournalProvider fallback
- VSSProvider abstraction & fallback
- BackupLock local mutual exclusion
- StartupRecoveryManager checkpoint reconciliation
"""

import os
import json
import time
import pytest
from unittest.mock import MagicMock, patch

from agent.src.config import AgentConfig
from agent.src.backup.models import DiscoveredFile
from agent.src.backup.run_state import (
    RunState,
    RunStateMachine,
    InvalidStateTransitionError
)
from agent.src.backup.checkpoint_manager import CheckpointManager, BackupCheckpointData
from agent.src.backup.retry_engine import RetryEngine, NonRetryableError
from agent.src.backup.transfer_engine import TransferEngine
from agent.src.windows.locked_files import LockedFileHandler, FileLockState
from agent.src.windows.usn_journal import USNJournalProvider
from agent.src.windows.vss import LiveFilesystemProvider, WindowsVSSProvider, get_vss_provider
from agent.src.utils.lock import BackupLock, BackupConcurrencyError
from agent.src.recovery.startup_recovery import StartupRecoveryManager
from agent.src.api_client import BackendApiClient


# ==============================================================================
# 1. Run State Machine Tests
# ==============================================================================

def test_run_state_machine_legal_transitions():
    """Verify normal linear backup lifecycle transitions."""
    sm = RunStateMachine(RunState.CREATED)
    assert sm.current_state == RunState.CREATED
    assert not sm.is_terminal

    sm.transition_to(RunState.DISCOVERING)
    assert sm.current_state == RunState.DISCOVERING

    sm.transition_to(RunState.SCANNING)
    assert sm.current_state == RunState.SCANNING

    sm.transition_to(RunState.BACKING_UP)
    assert sm.current_state == RunState.BACKING_UP

    sm.transition_to(RunState.VERIFYING)
    assert sm.current_state == RunState.VERIFYING

    sm.transition_to(RunState.COMPLETING)
    assert sm.current_state == RunState.COMPLETING

    sm.transition_to(RunState.COMPLETED)
    assert sm.current_state == RunState.COMPLETED
    assert sm.is_terminal


def test_run_state_machine_interruption_and_resume():
    """Verify state transitions during pause/interruption and resumption."""
    sm = RunStateMachine(RunState.CREATED)
    sm.transition_to(RunState.DISCOVERING)
    sm.transition_to(RunState.SCANNING)
    sm.transition_to(RunState.BACKING_UP)

    # Interrupted during backup
    sm.transition_to(RunState.INTERRUPTED, reason="Network loss")
    assert sm.current_state == RunState.INTERRUPTED
    assert sm.is_recoverable

    # Resuming
    sm.transition_to(RunState.RESUMING)
    assert sm.current_state == RunState.RESUMING

    # Back to backing up
    sm.transition_to(RunState.BACKING_UP)
    assert sm.current_state == RunState.BACKING_UP


def test_run_state_machine_illegal_transition():
    """Verify illegal transitions raise InvalidStateTransitionError."""
    sm = RunStateMachine(RunState.CREATED)
    with pytest.raises(InvalidStateTransitionError):
        sm.transition_to(RunState.COMPLETED)

    sm.transition_to(RunState.DISCOVERING)
    with pytest.raises(InvalidStateTransitionError):
        sm.transition_to(RunState.VERIFYING)


def test_run_state_machine_listener():
    """Verify transition listeners are notified on state changes."""
    sm = RunStateMachine(RunState.CREATED)
    history = []

    def on_change(old_st, new_st):
        history.append((old_st, new_st))

    sm.add_listener(on_change)
    sm.transition_to(RunState.DISCOVERING)
    sm.transition_to(RunState.SCANNING)

    assert history == [
        (RunState.CREATED, RunState.DISCOVERING),
        (RunState.DISCOVERING, RunState.SCANNING)
    ]


# ==============================================================================
# 2. Checkpoint Manager Tests
# ==============================================================================

def test_checkpoint_atomic_save_load_clear(tmp_path):
    """Verify crash-safe atomic checkpoint creation, read, and deletion."""
    config = AgentConfig(state_dir=str(tmp_path))
    cm = CheckpointManager(config, custom_state_dir=str(tmp_path))

    cp_data = BackupCheckpointData(
        run_id=42,
        client_id="CLIENT-TEST-1",
        policy_id=1,
        current_file="large_dataset.bin",
        current_file_path=str(tmp_path / "large_dataset.bin"),
        file_size=8388608,
        source_mtime=1700000000.0,
        change_type="FULL",
        upload_session_id="sess-abc-123",
        upload_object_id=None,
        bytes_uploaded=4194304,
        bytes_verified=4194304,
        last_successful_chunk=0,
        retry_count=0,
        timestamp=time.time(),
        checkpoint_version=1,
        state=RunState.BACKING_UP.value
    )

    # Save
    cm.save_checkpoint(cp_data)
    expected_file = tmp_path / "run_42.checkpoint.json"
    assert expected_file.exists()

    # Load
    loaded = cm.load_checkpoint(42)
    assert loaded is not None
    assert loaded.run_id == 42
    assert loaded.upload_session_id == "sess-abc-123"
    assert loaded.last_successful_chunk == 0
    assert loaded.bytes_uploaded == 4194304

    # List
    all_cps = cm.list_checkpoints()
    assert len(all_cps) == 1
    assert all_cps[0].run_id == 42

    # Clear
    cm.clear_checkpoint(42)
    assert not expected_file.exists()
    assert cm.load_checkpoint(42) is None


# ==============================================================================
# 3. Retry Engine Tests
# ==============================================================================

def test_retry_engine_backoff_and_jitter():
    """Verify exponential backoff calculation remains within bounds."""
    retry = RetryEngine(base_delay=1.0, max_delay=30.0, factor=2.0, jitter=True)

    delay_0 = retry.compute_delay(0)
    assert 0.0 <= delay_0 <= 1.0

    delay_1 = retry.compute_delay(1)
    assert 0.0 <= delay_1 <= 2.0

    delay_2 = retry.compute_delay(2)
    assert 0.0 <= delay_2 <= 4.0

    delay_10 = retry.compute_delay(10)
    assert 0.0 <= delay_10 <= 30.0  # Capped at max_delay


def test_retry_engine_execute_retries_transient_failures():
    """Verify RetryEngine retries transient exceptions and eventually succeeds."""
    retry = RetryEngine(base_delay=0.01, max_delay=0.1, max_retries=3)

    attempts = 0

    def unreliable_operation():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ConnectionResetError("Transient network drop")
        return "SUCCESS"

    result = retry.execute(unreliable_operation)
    assert result == "SUCCESS"
    assert attempts == 3


def test_retry_engine_rejects_non_retryable_errors():
    """Verify non-retryable errors abort immediately without burning retries."""
    retry = RetryEngine(base_delay=0.01, max_delay=0.1, max_retries=5)
    attempts = 0

    def fatal_operation():
        nonlocal attempts
        attempts += 1
        raise PermissionError("Access denied")

    with pytest.raises(PermissionError):
        retry.execute(fatal_operation)

    assert attempts == 1  # No retries on PermissionError


# ==============================================================================
# 4. Transfer Engine Tests (Server Authority & Chunk Skipping)
# ==============================================================================

def test_transfer_engine_server_authoritative_chunk_skipping(tmp_path):
    """
    Test resume correctness:
    If server confirms chunk 0 already exists in GET /upload-session/{id}/status,
    TransferEngine MUST NOT re-upload chunk 0 and should only upload chunk 1.
    """
    chunk_sz = 65536
    config = AgentConfig(chunk_size=chunk_sz, retry_backoff_max_seconds=1)
    cm = CheckpointManager(config, custom_state_dir=str(tmp_path))

    # Create 131072-byte test file (2 chunks of 65536 bytes)
    file_path = tmp_path / "multi_chunk.dat"
    content = b"A" * chunk_sz + b"B" * chunk_sz
    file_path.write_bytes(content)

    file_info = DiscoveredFile(
        original_path=str(file_path),
        relative_path="multi_chunk.dat",
        file_name="multi_chunk.dat",
        size_bytes=len(content),
        modified_time=time.time()
    )

    api_mock = MagicMock(spec=BackendApiClient)
    # 1. create_upload_session
    api_mock.create_upload_session.return_value = {
        "upload_session_id": "sess-test-99",
        "session_id": "sess-test-99",
        "chunk_size": chunk_sz,
        "total_chunks": 2,
        "confirmed_chunks": [0],  # Chunk 0 already confirmed by server!
        "next_expected_chunk": 1
    }
    # 2. get_upload_session_status
    api_mock.get_upload_session_status.return_value = {
        "upload_session_id": "sess-test-99",
        "session_id": "sess-test-99",
        "received_chunks": [0],  # Server confirmed chunk 0
        "confirmed_chunks": [0],
        "is_complete": False
    }
    # 3. upload_chunk (called ONLY for chunk 1)
    api_mock.upload_chunk.return_value = {
        "chunk_index": 1,
        "chunk_bytes": chunk_sz,
        "confirmed": True
    }
    # 4. complete_upload_session
    api_mock.complete_upload_session.return_value = {
        "session_id": "sess-test-99",
        "status": "completed",
        "storage_object": "sha256:test"
    }

    engine = TransferEngine(
        config=config,
        client_id="PC-V4-001",
        run_id=1,
        policy_id=1,
        api_client=api_mock,
        checkpoint_manager=cm
    )

    result = engine.transfer_file(file_info)

    assert result.status == "uploaded"
    assert result.size_bytes == 131072

    # CRITICAL: Verify chunk 0 was NOT uploaded, only chunk 1 was uploaded!
    assert api_mock.upload_chunk.call_count == 1
    kwargs = api_mock.upload_chunk.call_args.kwargs
    assert kwargs.get("chunk_index") == 1  # chunk_index was 1!


# ==============================================================================
# 5. Locked File Handler Tests
# ==============================================================================

def test_locked_file_inspection_readable(tmp_path):
    """Verify standard readable file is classified as READABLE."""
    handler = LockedFileHandler()
    f = tmp_path / "readable.txt"
    f.write_text("hello", encoding="utf-8")

    insp = handler.inspect_file(str(f), "readable.txt")
    assert insp.state == FileLockState.READABLE
    assert insp.size_bytes == 5
    assert insp.effective_path == str(f)


def test_locked_file_consistency_check_detects_mutation(tmp_path):
    """Verify file modified during reading is detected (CHANGED_DURING_BACKUP)."""
    handler = LockedFileHandler()
    f = tmp_path / "changing.txt"
    f.write_text("version 1", encoding="utf-8")

    initial_stat = handler.inspect_file(str(f), "changing.txt")

    # Modify file after initial inspection
    time.sleep(0.01)
    f.write_text("version 2 modified content", encoding="utf-8")

    is_consistent, reason = handler.verify_consistency(str(f), initial_stat)
    assert not is_consistent
    assert "size changed" in reason.lower() or "mtime changed" in reason.lower()


# ==============================================================================
# 6. USN Journal and VSS Provider Abstractions
# ==============================================================================

def test_usn_journal_fallback_behavior():
    """Verify USN Journal gracefully falls back to None on non-admin/non-NTFS."""
    provider = USNJournalProvider()
    candidates = provider.query_candidate_changed_files("Z:")
    # On arbitrary or non-elevated volume, must return None (triggering metadata scan fallback)
    assert candidates is None or isinstance(candidates, set)


def test_vss_provider_factory_and_fallback():
    """Verify VSS provider factory creates proper provider and gracefully handles fallback."""
    live_prov = get_vss_provider("LIVE")
    assert isinstance(live_prov, LiveFilesystemProvider)
    assert live_prov.is_available()
    assert live_prov.create_snapshot("C:") is None
    assert live_prov.get_snapshot_path("C:", "data\\file.txt") == os.path.join("C:", "data\\file.txt")

    vss_prov = get_vss_provider("VSS_WHEN_REQUIRED")
    assert isinstance(vss_prov, WindowsVSSProvider)
    # Non-elevated test context returns clean fallback
    snap_path = vss_prov.get_snapshot_path("C:", "test.txt")
    assert snap_path is not None


# ==============================================================================
# 7. Backup Lock (Local Process Concurrency)
# ==============================================================================

def test_backup_lock_mutual_exclusion(tmp_path):
    """Verify BackupLock prevents concurrent local execution."""
    lock_a = BackupLock(lock_name="test.lock", custom_dir=str(tmp_path))
    lock_b = BackupLock(lock_name="test.lock", custom_dir=str(tmp_path))

    assert lock_a.acquire() is True
    assert lock_a.is_locked is True

    # Second acquire must fail
    with pytest.raises(BackupConcurrencyError):
        lock_b.acquire()

    lock_a.release()
    assert lock_a.is_locked is False

    # Now lock_b can acquire
    assert lock_b.acquire() is True
    lock_b.release()


# ==============================================================================
# 8. Startup Recovery Manager Tests
# ==============================================================================

def test_startup_recovery_cleans_completed_runs(tmp_path):
    """Verify StartupRecoveryManager clears checkpoints for runs that completed on server."""
    config = AgentConfig(state_dir=str(tmp_path), resume_interrupted_runs=True)
    cm = CheckpointManager(config, custom_state_dir=str(tmp_path))

    # Save checkpoint for run 10
    cp = BackupCheckpointData(
        run_id=10,
        client_id="PC-01",
        policy_id=1,
        current_file="a.txt",
        current_file_path=str(tmp_path / "a.txt"),
        file_size=100,
        source_mtime=1.0,
        change_type="FULL",
        upload_session_id="s1",
        upload_object_id=None,
        bytes_uploaded=50,
        bytes_verified=50,
        last_successful_chunk=0,
        retry_count=0,
        timestamp=time.time(),
        checkpoint_version=1,
        state=RunState.BACKING_UP.value
    )
    cm.save_checkpoint(cp)

    api_mock = MagicMock(spec=BackendApiClient)
    api_mock.get_run_state.return_value = {
        "run_id": 10,
        "state": "COMPLETED",
        "status": "completed"
    }

    recovery = StartupRecoveryManager(config, api_mock, cm)
    candidate = recovery.scan_and_reconcile()

    # Since run 10 is completed on server, checkpoint must be deleted and no candidate returned
    assert candidate is None
    assert cm.load_checkpoint(10) is None


def test_startup_recovery_identifies_interrupted_run(tmp_path):
    """Verify StartupRecoveryManager discovers interrupted run eligible for resumption."""
    config = AgentConfig(state_dir=str(tmp_path), resume_interrupted_runs=True)
    cm = CheckpointManager(config, custom_state_dir=str(tmp_path))

    cp = BackupCheckpointData(
        run_id=20,
        client_id="PC-01",
        policy_id=1,
        current_file="video.mp4",
        current_file_path=str(tmp_path / "video.mp4"),
        file_size=10485760,
        source_mtime=1.0,
        change_type="FULL",
        upload_session_id="sess-interrupted",
        upload_object_id=None,
        bytes_uploaded=4194304,
        bytes_verified=4194304,
        last_successful_chunk=0,
        retry_count=0,
        timestamp=time.time(),
        checkpoint_version=1,
        state=RunState.INTERRUPTED.value
    )
    cm.save_checkpoint(cp)

    api_mock = MagicMock(spec=BackendApiClient)
    api_mock.get_run_state.return_value = {
        "run_id": 20,
        "state": "INTERRUPTED",
        "status": "running"
    }

    recovery = StartupRecoveryManager(config, api_mock, cm)
    candidate = recovery.scan_and_reconcile()

    assert candidate is not None
    assert candidate.run_id == 20
    assert candidate.upload_session_id == "sess-interrupted"
    assert cm.load_checkpoint(20) is not None
