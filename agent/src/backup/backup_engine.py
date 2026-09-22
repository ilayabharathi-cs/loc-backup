"""Backup Engine V2: Coordinates Initial Full File Backup execution."""

import time
import threading
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
from agent.src.logger import get_logger


class BackupEngine:
    """Executes initial full file backups and synchronizes state with the control plane."""

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

    def run_full_backup(
        self,
        resolved_policy: ResolvedPolicy,
        stop_event: Optional[threading.Event] = None
    ) -> BackupRunSummary:
        """Execute a complete initial full file backup according to the resolved policy."""
        if not self.identity.client_id:
            raise ValueError("Agent must be registered and have an assigned client_id before starting backup.")

        self.is_running = True
        start_time = time.time()
        self.logger.info("=" * 60)
        self.logger.info(f"Initiating Full File Backup for Policy: '{resolved_policy.policy_name}'")
        self.logger.info(f"Target Roots ({len(resolved_policy.valid_paths)}): {resolved_policy.valid_paths}")
        self.logger.info("=" * 60)

        # 1. Discover files across resolved include roots
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

        # 2. Initialize backup run on server
        run_payload = {
            "client_id": self.identity.client_id,
            "policy_id": resolved_policy.policy_id,
            "backup_type": BackupType.FULL.value,
            "files_discovered": len(discovered_files),
            "bytes_total": total_bytes
        }

        try:
            res = self.api_client._make_request("POST", "/backups/runs", run_payload)
            if not res.get("success"):
                raise ApiClientError(f"Could not create backup run: {res.get('error') or res.get('message')}")
            run_data = res.get("data", {})
            run_id = run_data.get("id")
            self.logger.info(f"Backup run created on control plane with ID: {run_id}")
        except Exception as e:
            self.logger.error(f"Failed to initialize backup run on server: {e}")
            self.is_running = False
            return BackupRunSummary(
                run_id=0,
                client_id=self.identity.client_id,
                status="failed",
                files_discovered=len(discovered_files),
                files_uploaded=0,
                files_failed=len(discovered_files),
                bytes_total=total_bytes,
                bytes_uploaded=0,
                duration_seconds=round(time.time() - start_time, 2),
                error_message=str(e)
            )

        # 3. Stream files to server
        uploader = FileUploader(self.config, self.identity.client_id, run_id)
        files_uploaded = 0
        files_failed = 0
        bytes_uploaded = 0
        error_count = 0
        last_progress_update = time.time()

        for idx, file_obj in enumerate(discovered_files):
            if stop_event and stop_event.is_set():
                self.logger.warning("Backup interrupted by service stop event.")
                break

            result = uploader.upload_file(file_obj)

            if result.status == "uploaded":
                files_uploaded += 1
                bytes_uploaded += result.size_bytes
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
                            "error_count": error_count
                        }
                    )
                except Exception:
                    pass

        # 4. Finalize backup run
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
                    "error_count": error_count,
                    "error_message": f"{files_failed} files failed or locked" if files_failed > 0 else None
                }
            )
            recovery_point_created = (final_status == "completed")
        except Exception as e:
            self.logger.error(f"Error completing backup run on server: {e}")
            recovery_point_created = False

        self.is_running = False
        summary = BackupRunSummary(
            run_id=run_id,
            client_id=self.identity.client_id,
            status=final_status,
            files_discovered=len(discovered_files),
            files_uploaded=files_uploaded,
            files_failed=files_failed,
            bytes_total=total_bytes,
            bytes_uploaded=bytes_uploaded,
            duration_seconds=duration,
            recovery_point_created=recovery_point_created
        )

        self.logger.info("=" * 60)
        self.logger.info(f"Full Backup Finished: Status={summary.status}, Duration={summary.duration_seconds}s")
        self.logger.info("=" * 60)
        return summary
