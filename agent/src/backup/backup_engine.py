"""Backup Engine V4: Coordinates Initial Full & Metadata-Based Incremental Backups
with state machine tracking, chunked resumable transfers, locked file handling,
local mutual exclusion, and crash-safe checkpoints.
"""

import os
import time
import threading
import datetime
from typing import Optional, Dict, Any, List
from concurrent.futures import ThreadPoolExecutor, as_completed

from agent.src.config import AgentConfig
from agent.src.identity import DeviceIdentity
from agent.src.api_client import BackendApiClient, ApiClientError
from agent.src.policy_resolver import PolicyResolver, ResolvedPolicy
from agent.src.backup.models import (
    BackupType,
    DiscoveredFile,
    FileUploadResult,
    BackupProgress,
    BackupRunSummary
)
from agent.src.backup.scanner import FileScanner
from agent.src.backup.uploader import FileUploader
from agent.src.backup.change_detector import ChangeDetector, FileState, ChangeDetectionResult
from agent.src.backup.run_state import RunState, RunStateMachine
from agent.src.backup.checkpoint_manager import CheckpointManager
from agent.src.backup.retry_engine import RetryEngine
from agent.src.backup.transfer_engine import TransferEngine
from agent.src.windows.vss import VSSProvider, get_vss_provider
from agent.src.windows.usn_journal import USNJournalProvider
from agent.src.windows.locked_files import LockedFileHandler, FileLockState
from agent.src.utils.lock import BackupLock, BackupConcurrencyError
from agent.src.logger import get_logger


class BackupEngine:
    """Executes full and incremental backups and synchronizes state with the control plane."""

    def __init__(
        self,
        config: AgentConfig,
        identity: DeviceIdentity,
        api_client: BackendApiClient,
        max_workers: int = 2
    ):
        self.config = config
        self.identity = identity
        self.api_client = api_client
        self.max_workers = max_workers
        self.logger = get_logger()
        self.is_running = False

        # V4 Reliability Components
        self.checkpoint_manager = CheckpointManager(config)
        self.backup_lock = BackupLock()
        self.vss_provider = get_vss_provider(getattr(config, "consistency_mode", "LIVE"))
        self.usn_provider = USNJournalProvider()
        self.locked_file_handler = LockedFileHandler(vss_provider=self.vss_provider)
        self.retry_engine = RetryEngine(
            base_delay=1.0,
            max_delay=float(getattr(config, "retry_backoff_max_seconds", 30.0)),
            factor=2.0
        )

    def run_full_backup(
        self,
        resolved_policy: ResolvedPolicy,
        stop_event: Optional[threading.Event] = None
    ) -> BackupRunSummary:
        """Execute a complete initial full file backup according to the resolved policy."""
        if not self.identity.client_id:
            raise ValueError("Agent must be registered and have an assigned client_id before starting backup.")

        # Local mutual exclusion
        if not self.backup_lock.acquire():
            raise BackupConcurrencyError("Another backup operation is currently active on this agent.")

        state_machine = RunStateMachine(RunState.CREATED)
        self.is_running = True
        start_time = time.time()
        run_id = 0
        total_bytes = 0
        discovered_files: List[DiscoveredFile] = []

        try:
            self.logger.info("=" * 60)
            self.logger.info(f"Initiating Full File Backup for Policy: '{resolved_policy.policy_name}'")
            self.logger.info(f"Target Roots ({len(resolved_policy.valid_paths)}): {resolved_policy.valid_paths}")
            self.logger.info("=" * 60)

            # 1. Discover files across resolved include roots
            state_machine.transition(RunState.DISCOVERING)
            scanner = FileScanner(
                include_paths=resolved_policy.valid_paths,
                exclude_paths=resolved_policy.excluded_paths
            )
            discovered_files = scanner.scan()
            total_bytes = sum(f.size_bytes for f in discovered_files if f.is_accessible)

            self.logger.info(
                f"File discovery finished: {len(discovered_files)} files, "
                f"{round(total_bytes / (1024 * 1024), 2)} MB total."
            )

            # 2. Scanning & Run Initialization
            state_machine.transition(RunState.SCANNING)
            run_payload = {
                "client_id": self.identity.client_id,
                "policy_id": resolved_policy.policy_id,
                "backup_type": BackupType.FULL.value,
                "files_discovered": len(discovered_files),
                "bytes_total": total_bytes,
                "prevent_concurrent": True
            }

            try:
                res = self.api_client._make_request("POST", "/backups/runs", run_payload)
                if not res.get("success"):
                    raise ApiClientError(f"Could not create backup run: {res.get('error') or res.get('message')}")
                run_data = res.get("data", {})
                run_id = run_data.get("id")
                self.logger.info(f"Backup run created on control plane with ID: {run_id}")
                try:
                    self.api_client.update_run_state(run_id, RunState.SCANNING.value)
                except Exception:
                    pass
            except Exception as e:
                self.logger.error(f"Failed to initialize backup run on server: {e}")
                state_machine.transition(RunState.FAILED)
                return BackupRunSummary(
                    run_id=0,
                    client_id=self.identity.client_id,
                    status="failed",
                    state=RunState.FAILED.value,
                    backup_type=BackupType.FULL.value,
                    files_discovered=len(discovered_files),
                    files_uploaded=0,
                    files_failed=len(discovered_files),
                    bytes_total=total_bytes,
                    bytes_uploaded=0,
                    duration_seconds=round(time.time() - start_time, 2),
                    error_message=str(e)
                )

            # 3. Stream files to server using chunked resumable transfers
            state_machine.transition(RunState.BACKING_UP)
            try:
                self.api_client.update_run_state(run_id, RunState.BACKING_UP.value)
            except Exception:
                pass

            uploader = FileUploader(self.config, self.identity.client_id, run_id)
            transfer_engine = TransferEngine(
                config=self.config,
                client_id=self.identity.client_id,
                run_id=run_id,
                policy_id=resolved_policy.policy_id,
                api_client=self.api_client,
                checkpoint_manager=self.checkpoint_manager,
                retry_engine=self.retry_engine,
                locked_file_handler=self.locked_file_handler
            )
            uploader.transfer_engine = transfer_engine

            files_uploaded = 0
            files_failed = 0
            files_locked = 0
            files_vss_recovered = 0
            bytes_uploaded = 0
            error_count = 0
            last_progress_update = time.time()
            interrupted = False

            for idx, file_obj in enumerate(discovered_files):
                if stop_event and stop_event.is_set():
                    self.logger.warning("Backup interrupted by service stop event.")
                    state_machine.transition(RunState.INTERRUPTED)
                    try:
                        self.api_client.interrupt_run(run_id)
                    except Exception:
                        pass
                    interrupted = True
                    break

                result = uploader.upload_file(file_obj, change_type="FULL")

                if result.status == "uploaded":
                    files_uploaded += 1
                    bytes_uploaded += result.size_bytes
                elif result.status == "vss_recovered":
                    files_uploaded += 1
                    files_vss_recovered += 1
                    bytes_uploaded += result.size_bytes
                elif result.status == "locked":
                    files_locked += 1
                    files_failed += 1
                    error_count += 1
                    self.logger.warning(f"File locked: '{result.file_name}': {result.error_message}")
                else:
                    files_failed += 1
                    error_count += 1
                    self.logger.warning(
                        f"File upload status '{result.status}' for '{result.file_name}': {result.error_message}"
                    )

                # Periodically update progress every 3 seconds or on milestones
                now = time.time()
                if now - last_progress_update >= 3.0 or idx == len(discovered_files) - 1:
                    last_progress_update = now
                    try:
                        self.api_client._make_request(
                            "POST",
                            f"/backups/runs/{run_id}/progress",
                            {
                                "files_discovered": len(discovered_files),
                                "files_uploaded": files_uploaded,
                                "files_failed": files_failed,
                                "bytes_total": total_bytes,
                                "bytes_uploaded": bytes_uploaded,
                                "current_file": file_obj.file_name,
                                "error_count": error_count,
                                "files_locked": files_locked,
                                "files_vss_recovered": files_vss_recovered
                            }
                        )
                    except Exception:
                        pass

            if interrupted:
                duration = round(time.time() - start_time, 2)
                return BackupRunSummary(
                    run_id=run_id,
                    client_id=self.identity.client_id,
                    status="interrupted",
                    state=RunState.INTERRUPTED.value,
                    backup_type=BackupType.FULL.value,
                    files_discovered=len(discovered_files),
                    files_uploaded=files_uploaded,
                    files_failed=files_failed,
                    files_locked=files_locked,
                    files_vss_recovered=files_vss_recovered,
                    bytes_total=total_bytes,
                    bytes_uploaded=bytes_uploaded,
                    duration_seconds=duration,
                    checkpoint_saved=True,
                    error_message="Interrupted by stop event"
                )

            # 4. Finalize backup run
            state_machine.transition(RunState.VERIFYING)
            try:
                self.api_client.update_run_state(run_id, RunState.VERIFYING.value)
            except Exception:
                pass

            state_machine.transition(RunState.COMPLETING)
            try:
                self.api_client.update_run_state(run_id, RunState.COMPLETING.value)
            except Exception:
                pass

            duration = round(time.time() - start_time, 2)
            final_status = "completed" if (files_failed == 0 or files_uploaded > 0) else "failed"

            try:
                self.logger.info(
                    f"Completing backup run {run_id}. Final status: {final_status}. "
                    f"Uploaded: {files_uploaded}/{len(discovered_files)}, Failed: {files_failed}."
                )
                complete_res = self.api_client._make_request(
                    "POST",
                    f"/backups/runs/{run_id}/complete",
                    {
                        "status": final_status,
                        "files_uploaded": files_uploaded,
                        "files_failed": files_failed,
                        "bytes_uploaded": bytes_uploaded,
                        "files_discovered": len(discovered_files),
                        "bytes_total": total_bytes,
                        "files_new": files_uploaded,
                        "files_modified": 0,
                        "files_unchanged": 0,
                        "files_deleted": 0,
                        "files_locked": files_locked,
                        "files_vss_recovered": files_vss_recovered,
                        "error_count": error_count,
                        "error_message": f"{files_failed} files failed or locked" if files_failed > 0 else None
                    }
                )
                recovery_point_created = (final_status == "completed" and complete_res.get("success", False))
                if final_status == "completed":
                    state_machine.transition(RunState.COMPLETED)
                    self.checkpoint_manager.clear_checkpoint(run_id)
                else:
                    state_machine.transition(RunState.FAILED)
            except Exception as e:
                self.logger.error(f"Error completing backup run on server: {e}")
                recovery_point_created = False
                state_machine.transition(RunState.FAILED)

            summary = BackupRunSummary(
                run_id=run_id,
                client_id=self.identity.client_id,
                status=final_status,
                state=state_machine.current_state.value,
                backup_type=BackupType.FULL.value,
                files_discovered=len(discovered_files),
                files_uploaded=files_uploaded,
                files_failed=files_failed,
                files_new=files_uploaded,
                files_modified=0,
                files_unchanged=0,
                files_deleted=0,
                files_locked=files_locked,
                files_vss_recovered=files_vss_recovered,
                bytes_total=total_bytes,
                bytes_uploaded=bytes_uploaded,
                duration_seconds=duration,
                recovery_point_created=recovery_point_created
            )

            self.logger.info("=" * 60)
            self.logger.info(f"Full Backup Finished: Status={summary.status}, Duration={summary.duration_seconds}s")
            self.logger.info("=" * 60)
            return summary

        finally:
            self.is_running = False
            self.backup_lock.release()

    def run_incremental_backup(
        self,
        resolved_policy: ResolvedPolicy,
        stop_event: Optional[threading.Event] = None,
        change_detection_mode: str = "metadata"
    ) -> BackupRunSummary:
        """
        Execute an incremental backup according to resolved policy and baseline Recovery Point.
        Uploads ONLY NEW and MODIFIED files; unchanged files are referenced via immutable objects.
        """
        if not self.identity.client_id:
            raise ValueError("Agent must be registered and have an assigned client_id before starting backup.")

        # Local mutual exclusion
        if not self.backup_lock.acquire():
            raise BackupConcurrencyError("Another backup operation is currently active on this agent.")

        state_machine = RunStateMachine(RunState.CREATED)
        self.is_running = True
        start_time = time.time()
        run_id = 0

        try:
            self.logger.info("=" * 60)
            self.logger.info("Incremental backup started")

            # STEP 1: Load latest successful Recovery Point baseline
            state_machine.transition(RunState.DISCOVERING)
            baseline_rp = self.api_client.get_latest_recovery_point(
                client_id=self.identity.client_id,
                policy_id=resolved_policy.policy_id
            )

            if not baseline_rp or not baseline_rp.get("id"):
                err_msg = "No valid full backup baseline exists. Run a full backup first."
                self.logger.error(err_msg)
                state_machine.transition(RunState.FAILED)
                raise ValueError(err_msg)

            baseline_rp_id = baseline_rp["id"]
            baseline_run_id = baseline_rp.get("backup_run_id")
            self.logger.info(f"Baseline: Recovery Point #{baseline_rp_id} (Run #{baseline_run_id})")

            # STEP 2: Scan current filesystem (with USN Journal candidate path acceleration if requested)
            self.logger.info("Scanning...")
            if change_detection_mode == "usn" or getattr(self.config, "enable_usn_journal", False):
                for vp in resolved_policy.valid_paths:
                    vol = os.path.splitdrive(vp)[0]
                    if vol:
                        self.usn_provider.query_candidate_changed_files(vol)

            scanner = FileScanner(
                include_paths=resolved_policy.valid_paths,
                exclude_paths=resolved_policy.excluded_paths
            )
            discovered_files = scanner.scan()
            self.logger.info(f"Files discovered: {len(discovered_files)}")

            # STEP 3: Load baseline manifest from server
            try:
                manifest_data = self.api_client.get_recovery_point_manifest(baseline_rp_id, include_deleted=True)
                baseline_manifest = manifest_data.get("files", [])
            except Exception as e:
                self.logger.error(f"Failed to fetch baseline manifest: {e}")
                state_machine.transition(RunState.FAILED)
                return BackupRunSummary(
                    run_id=0,
                    client_id=self.identity.client_id,
                    status="failed",
                    state=RunState.FAILED.value,
                    backup_type=BackupType.INCREMENTAL.value,
                    files_discovered=len(discovered_files),
                    files_uploaded=0,
                    files_failed=len(discovered_files),
                    bytes_total=0,
                    bytes_uploaded=0,
                    duration_seconds=round(time.time() - start_time, 2),
                    error_message=f"Failed to fetch baseline manifest: {e}"
                )

            # STEP 4: Compare current filesystem against baseline manifest
            state_machine.transition(RunState.SCANNING)
            detector = ChangeDetector(mode=change_detection_mode)
            changes: ChangeDetectionResult = detector.detect_changes(discovered_files, baseline_manifest)

            self.logger.info(
                f"Changes:\n"
                f"NEW: {len(changes.new_files)}\n"
                f"MODIFIED: {len(changes.modified_files)}\n"
                f"UNCHANGED: {len(changes.unchanged_files)}\n"
                f"DELETED: {len(changes.deleted_files)}"
            )

            # STEP 5: Initialize INCREMENTAL BackupRun on server
            run_payload = {
                "client_id": self.identity.client_id,
                "policy_id": resolved_policy.policy_id,
                "backup_type": BackupType.INCREMENTAL.value,
                "baseline_run_id": baseline_run_id,
                "files_discovered": len(discovered_files),
                "bytes_total": changes.total_logical_bytes,
                "prevent_concurrent": True
            }

            try:
                res = self.api_client._make_request("POST", "/backups/runs", run_payload)
                if not res.get("success"):
                    raise ApiClientError(f"Could not create incremental backup run: {res.get('error') or res.get('message')}")
                run_data = res.get("data", {})
                run_id = run_data.get("id")
                self.logger.info(f"Incremental backup run created on control plane with ID: {run_id}")
                try:
                    self.api_client.update_run_state(run_id, RunState.SCANNING.value)
                except Exception:
                    pass
            except Exception as e:
                self.logger.error(f"Failed to initialize incremental backup run: {e}")
                state_machine.transition(RunState.FAILED)
                return BackupRunSummary(
                    run_id=0,
                    client_id=self.identity.client_id,
                    status="failed",
                    state=RunState.FAILED.value,
                    backup_type=BackupType.INCREMENTAL.value,
                    files_discovered=len(discovered_files),
                    files_uploaded=0,
                    files_failed=len(changes.files_to_upload),
                    bytes_total=changes.total_logical_bytes,
                    bytes_uploaded=0,
                    duration_seconds=round(time.time() - start_time, 2),
                    error_message=str(e)
                )

            # STEP 6: Upload ONLY NEW and MODIFIED files using chunked resumable transfer
            state_machine.transition(RunState.BACKING_UP)
            try:
                self.api_client.update_run_state(run_id, RunState.BACKING_UP.value)
            except Exception:
                pass

            uploader = FileUploader(self.config, self.identity.client_id, run_id)
            transfer_engine = TransferEngine(
                config=self.config,
                client_id=self.identity.client_id,
                run_id=run_id,
                policy_id=resolved_policy.policy_id,
                api_client=self.api_client,
                checkpoint_manager=self.checkpoint_manager,
                retry_engine=self.retry_engine,
                locked_file_handler=self.locked_file_handler
            )
            uploader.transfer_engine = transfer_engine

            files_uploaded = 0
            files_failed = 0
            files_locked = 0
            files_vss_recovered = 0
            bytes_uploaded = 0
            error_count = 0
            files_to_upload = changes.files_to_upload
            last_progress_update = time.time()
            interrupted = False

            if files_to_upload:
                self.logger.info(f"Uploading {len(files_to_upload)} changed files...")

            for idx, classified in enumerate(files_to_upload):
                if stop_event and stop_event.is_set():
                    self.logger.warning("Backup interrupted by service stop event.")
                    state_machine.transition(RunState.INTERRUPTED)
                    try:
                        self.api_client.interrupt_run(run_id)
                    except Exception:
                        pass
                    interrupted = True
                    break

                self.logger.info(f"Uploading: {classified.file_name} ({classified.state.value})")
                result = uploader.upload_file(
                    classified.discovered_file,
                    change_type=classified.state.value
                )

                if result.status == "uploaded":
                    files_uploaded += 1
                    bytes_uploaded += result.size_bytes
                elif result.status == "vss_recovered":
                    files_uploaded += 1
                    files_vss_recovered += 1
                    bytes_uploaded += result.size_bytes
                elif result.status == "locked":
                    files_locked += 1
                    files_failed += 1
                    error_count += 1
                    self.logger.warning(f"File locked: '{result.file_name}': {result.error_message}")
                else:
                    files_failed += 1
                    error_count += 1
                    self.logger.warning(
                        f"File upload status '{result.status}' for '{result.file_name}': {result.error_message}"
                    )

                # Periodically update progress
                now = time.time()
                if now - last_progress_update >= 3.0 or idx == len(files_to_upload) - 1:
                    last_progress_update = now
                    try:
                        self.api_client._make_request(
                            "POST",
                            f"/backups/runs/{run_id}/progress",
                            {
                                "files_discovered": len(discovered_files),
                                "files_uploaded": files_uploaded,
                                "files_failed": files_failed,
                                "files_new": len(changes.new_files),
                                "files_modified": len(changes.modified_files),
                                "files_unchanged": len(changes.unchanged_files),
                                "files_deleted": len(changes.deleted_files),
                                "files_locked": files_locked,
                                "files_vss_recovered": files_vss_recovered,
                                "bytes_total": changes.total_logical_bytes,
                                "bytes_uploaded": bytes_uploaded,
                                "current_file": classified.file_name,
                                "error_count": error_count
                            }
                        )
                    except Exception:
                        pass

            if interrupted:
                duration = round(time.time() - start_time, 2)
                return BackupRunSummary(
                    run_id=run_id,
                    client_id=self.identity.client_id,
                    status="interrupted",
                    state=RunState.INTERRUPTED.value,
                    backup_type=BackupType.INCREMENTAL.value,
                    files_discovered=len(discovered_files),
                    files_uploaded=files_uploaded,
                    files_failed=files_failed,
                    files_new=len(changes.new_files),
                    files_modified=len(changes.modified_files),
                    files_unchanged=len(changes.unchanged_files),
                    files_deleted=len(changes.deleted_files),
                    files_locked=files_locked,
                    files_vss_recovered=files_vss_recovered,
                    bytes_total=changes.total_logical_bytes,
                    bytes_uploaded=bytes_uploaded,
                    duration_seconds=duration,
                    checkpoint_saved=True,
                    error_message="Interrupted by stop event"
                )

            # STEP 7: Batch-record UNCHANGED and DELETED metadata (referencing immutable objects)
            metadata_records = []

            # Record UNCHANGED files (pointing to previous storage objects)
            for uf in changes.unchanged_files:
                mtime_iso = None
                if uf.modified_time:
                    mtime_iso = datetime.datetime.fromtimestamp(uf.modified_time, datetime.timezone.utc).isoformat()

                metadata_records.append({
                    "original_path": uf.original_path,
                    "relative_path": uf.relative_path,
                    "file_name": uf.file_name,
                    "size_bytes": uf.size_bytes,
                    "sha256": uf.sha256,
                    "storage_object": uf.storage_object,
                    "change_type": "UNCHANGED",
                    "upload_status": "completed",
                    "modified_time": mtime_iso
                })

            # Record DELETED files (tombstone metadata, storage_object=None)
            for df in changes.deleted_files:
                mtime_iso = None
                if df.modified_time:
                    mtime_iso = datetime.datetime.fromtimestamp(df.modified_time, datetime.timezone.utc).isoformat()

                metadata_records.append({
                    "original_path": df.original_path,
                    "relative_path": df.relative_path,
                    "file_name": df.file_name,
                    "size_bytes": df.size_bytes,
                    "sha256": df.sha256,
                    "storage_object": None,
                    "change_type": "DELETED",
                    "upload_status": "deleted",
                    "modified_time": mtime_iso
                })

            if metadata_records:
                try:
                    self.api_client.record_run_metadata(run_id, metadata_records)
                    self.logger.info(
                        f"Successfully recorded metadata for {len(changes.unchanged_files)} unchanged "
                        f"and {len(changes.deleted_files)} deleted files."
                    )
                except Exception as e:
                    self.logger.error(f"Failed to record unchanged/deleted metadata: {e}")
                    files_failed += len(metadata_records)
                    error_count += 1

            # STEP 8: Finalize run with atomic validation on server
            state_machine.transition(RunState.VERIFYING)
            try:
                self.api_client.update_run_state(run_id, RunState.VERIFYING.value)
            except Exception:
                pass

            state_machine.transition(RunState.COMPLETING)
            try:
                self.api_client.update_run_state(run_id, RunState.COMPLETING.value)
            except Exception:
                pass

            duration = round(time.time() - start_time, 2)
            final_status = "completed" if (files_failed == 0) else "failed"

            try:
                self.logger.info(
                    f"Completing incremental backup run {run_id}. Final status: {final_status}. "
                    f"Uploaded: {files_uploaded}/{len(files_to_upload)}, Unchanged: {len(changes.unchanged_files)}, "
                    f"Deleted: {len(changes.deleted_files)}, Failed: {files_failed}."
                )
                complete_res = self.api_client._make_request(
                    "POST",
                    f"/backups/runs/{run_id}/complete",
                    {
                        "status": final_status,
                        "files_uploaded": files_uploaded,
                        "files_failed": files_failed,
                        "bytes_uploaded": bytes_uploaded,
                        "files_discovered": len(discovered_files),
                        "bytes_total": changes.total_logical_bytes,
                        "files_new": len(changes.new_files),
                        "files_modified": len(changes.modified_files),
                        "files_unchanged": len(changes.unchanged_files),
                        "files_deleted": len(changes.deleted_files),
                        "files_locked": files_locked,
                        "files_vss_recovered": files_vss_recovered,
                        "error_count": error_count,
                        "error_message": f"{files_failed} files failed or locked" if files_failed > 0 else None
                    }
                )
                msg = complete_res.get("message", "")
                recovery_point_created = (final_status == "completed" and "skipped" not in msg and complete_res.get("success", False))
                if not recovery_point_created:
                    self.logger.warning(f"Recovery Point creation skipped by server: {msg}")

                if final_status == "completed":
                    state_machine.transition(RunState.COMPLETED)
                    self.checkpoint_manager.clear_checkpoint(run_id)
                else:
                    state_machine.transition(RunState.FAILED)
            except Exception as e:
                self.logger.error(f"Error completing incremental backup run on server: {e}")
                recovery_point_created = False
                state_machine.transition(RunState.FAILED)

            summary = BackupRunSummary(
                run_id=run_id,
                client_id=self.identity.client_id,
                status=final_status,
                state=state_machine.current_state.value,
                backup_type=BackupType.INCREMENTAL.value,
                files_discovered=len(discovered_files),
                files_uploaded=files_uploaded,
                files_failed=files_failed,
                files_new=len(changes.new_files),
                files_modified=len(changes.modified_files),
                files_unchanged=len(changes.unchanged_files),
                files_deleted=len(changes.deleted_files),
                files_locked=files_locked,
                files_vss_recovered=files_vss_recovered,
                bytes_total=changes.total_logical_bytes,
                bytes_uploaded=bytes_uploaded,
                duration_seconds=duration,
                recovery_point_created=recovery_point_created
            )

            self.logger.info("=" * 60)
            self.logger.info(
                f"Incremental Backup Finished: Status={summary.status}, Duration={summary.duration_seconds}s\n"
                f"Completed: Uploaded: {summary.files_uploaded} files, Bytes: {round(summary.bytes_uploaded / (1024*1024), 2)} MB\n"
                f"Recovery Point Created: {summary.recovery_point_created}"
            )
            self.logger.info("=" * 60)
            return summary

        finally:
            self.is_running = False
            self.backup_lock.release()
