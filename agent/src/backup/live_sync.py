"""Continuous Background Live Sync & Directory Monitoring for RetroVault Agent.

Monitors active policy target folders continuously in the background.
Whenever files are added, modified, or updated, automatically triggers
an incremental backup to sync changes to the server in real-time.
"""

import os
import time
import threading
from typing import Optional, Dict, Tuple, Set, List, Callable
from agent.src.config import AgentConfig
from agent.src.identity import DeviceIdentity
from agent.src.api_client import BackendApiClient
from agent.src.policy_resolver import PolicyResolver, ResolvedPolicy
from agent.src.backup.backup_engine import BackupEngine
from agent.src.backup.scanner import FileScanner
from agent.src.logger import get_logger


class ContinuousSyncWorker:
    """
    Background worker thread monitoring target backup folders.
    Detects any added or modified files in real-time while the EXE runs in the background,
    and automatically triggers an incremental backup to synchronize updates to the server.
    """

    def __init__(
        self,
        config: AgentConfig,
        identity: DeviceIdentity,
        api_client: BackendApiClient,
        policy_provider: Callable[[], Optional[ResolvedPolicy]],
        stop_event: Optional[threading.Event] = None,
        scan_interval_seconds: float = 5.0,
        debounce_seconds: float = 3.0
    ):
        self.config = config
        self.identity = identity
        self.api_client = api_client
        self.policy_provider = policy_provider
        self.stop_event = stop_event or threading.Event()
        self.scan_interval = scan_interval_seconds
        self.debounce_seconds = debounce_seconds
        self.logger = get_logger()
        self._file_snapshots: Dict[str, Tuple[float, int]] = {}
        self._is_syncing = False
        self._pending_sync = False
        self._last_change_time = 0.0

    def _take_snapshot(self, paths: List[str], excluded: List[str]) -> Dict[str, Tuple[float, int]]:
        """Fast filesystem stat snapshot of watched directories (path -> (mtime, size))."""
        snapshot: Dict[str, Tuple[float, int]] = {}
        scanner = FileScanner(include_paths=paths, exclude_paths=excluded)
        files = scanner.scan()
        for f in files:
            if f.is_accessible:
                snapshot[f.original_path] = (f.modified_time, f.size_bytes)
        return snapshot

    def _detect_changes(self, new_snapshot: Dict[str, Tuple[float, int]]) -> Tuple[List[str], List[str], List[str]]:
        """Compare current snapshot against previous snapshot to identify added, modified, deleted files."""
        added = []
        modified = []
        deleted = []

        old_paths = set(self._file_snapshots.keys())
        new_paths = set(new_snapshot.keys())

        for p in new_paths - old_paths:
            added.append(p)

        for p in old_paths - new_paths:
            deleted.append(p)

        for p in new_paths & old_paths:
            old_mtime, old_size = self._file_snapshots[p]
            new_mtime, new_size = new_snapshot[p]
            if new_mtime != old_mtime or new_size != old_size:
                modified.append(p)

        return added, modified, deleted

    def run_sync(self, resolved_policy: ResolvedPolicy) -> None:
        """Execute a live backup to sync new or modified updates to the control plane."""
        if not self.identity.client_id:
            return

        self._is_syncing = True
        try:
            engine = BackupEngine(self.config, self.identity, self.api_client)
            # Check if a baseline full backup exists
            latest_rp = None
            try:
                latest_rp = self.api_client.get_latest_recovery_point(
                    client_id=self.identity.client_id,
                    policy_id=resolved_policy.policy_id
                )
            except Exception:
                pass

            if latest_rp and latest_rp.get("id"):
                self.logger.info("Live Sync: Syncing updates via incremental backup...")
                summary = engine.run_incremental_backup(resolved_policy, stop_event=self.stop_event)
                self.logger.info(
                    f"Live Sync: Incremental backup finished. "
                    f"Uploaded: {summary.files_uploaded} files, Status: {summary.status}"
                )
            else:
                self.logger.info("Live Sync: No prior baseline found; performing initial full backup...")
                summary = engine.run_full_backup(resolved_policy, stop_event=self.stop_event)
                self.logger.info(
                    f"Live Sync: Full backup completed. "
                    f"Uploaded: {summary.files_uploaded} files, Status: {summary.status}"
                )
        except Exception as e:
            self.logger.warning(f"Live Sync: Backup run encountered error: {e}")
        finally:
            self._is_syncing = False

    def run_loop(self) -> None:
        """Main continuous background watching loop."""
        self.logger.info("Starting continuous live folder watcher in background...")

        # Initial delay before starting checks to let agent complete registration
        time.sleep(2)

        while not self.stop_event.is_set():
            resolved = self.policy_provider()
            if not resolved or not resolved.valid_paths:
                # No active policy or paths yet; wait and retry
                if self.stop_event.wait(timeout=self.scan_interval):
                    break
                continue

            # First run: initialize baseline snapshot
            if not self._file_snapshots:
                self._file_snapshots = self._take_snapshot(resolved.valid_paths, resolved.excluded_paths)
                self.logger.info(
                    f"Live Folder Watcher: Initialized baseline snapshot for {len(self._file_snapshots)} files "
                    f"across {len(resolved.valid_paths)} watched target folders."
                )

                # Check if this client has any prior completed backup on the server
                has_baseline = False
                try:
                    latest_rp = self.api_client.get_latest_recovery_point(client_id=self.identity.client_id)
                    has_baseline = bool(latest_rp and latest_rp.get("id"))
                except Exception:
                    has_baseline = False

                if not has_baseline:
                    self.logger.info("Live Folder Watcher: No baseline backup found on server. Initiating initial backup immediately...")
                    self.run_sync(resolved)
                    self._file_snapshots = self._take_snapshot(resolved.valid_paths, resolved.excluded_paths)

            # Check for changes
            current_snapshot = self._take_snapshot(resolved.valid_paths, resolved.excluded_paths)
            added, modified, deleted = self._detect_changes(current_snapshot)

            if added or modified or deleted:
                now = time.time()
                self._last_change_time = now
                self._pending_sync = True
                self.logger.info(
                    f"Live Folder Watcher: Detected filesystem updates -> "
                    f"Added: {len(added)}, Modified: {len(modified)}, Deleted: {len(deleted)}. "
                    f"Debouncing for {self.debounce_seconds}s before syncing..."
                )
                self._file_snapshots = current_snapshot

            # If changes are pending and debounce time has passed, trigger sync
            if self._pending_sync and not self._is_syncing:
                if (time.time() - self._last_change_time) >= self.debounce_seconds:
                    self._pending_sync = False
                    self.logger.info("Live Folder Watcher: Debounce settled. Initiating live background backup...")
                    self.run_sync(resolved)
                    # Refresh snapshot after backup
                    self._file_snapshots = self._take_snapshot(resolved.valid_paths, resolved.excluded_paths)

            # Wait before next filesystem check
            if self.stop_event.wait(timeout=self.scan_interval):
                break

        self.logger.info("Continuous live folder watcher stopped cleanly.")
