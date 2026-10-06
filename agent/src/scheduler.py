"""Scheduler and backup orchestration foundation for RetroVault Cross-Platform Agent.

Handles:
- Scheduled backup triggers with next-run calculation
- Server-triggered "Backup Now" jobs
- Dual-trigger routing to the SAME BackupEngine
- Active-job detection and concurrency prevention
- Persistent local policy caching and offline fallback
- Platform-neutral execution across Windows and Linux
"""

import os
import json
import time
import threading
from typing import Optional, Dict, Any

from agent.src.config import AgentConfig
from agent.src.identity import DeviceIdentity
from agent.src.api_client import BackendApiClient, ApiClientError
from agent.src.policy_resolver import PolicyResolver, ResolvedPolicy
from agent.src.platform import get_platform_adapter, PlatformAdapter
from agent.src.backup.backup_engine import BackupEngine
from agent.src.logger import get_logger


class BackupScheduler:
    """Orchestrates periodic policy synchronization, scheduled runs, and server-triggered jobs."""

    def __init__(
        self,
        config: AgentConfig,
        identity: DeviceIdentity,
        api_client: BackendApiClient,
        stop_event: Optional[threading.Event] = None,
        platform_adapter: Optional[PlatformAdapter] = None
    ):
        self.config = config
        self.identity = identity
        self.api_client = api_client
        self.stop_event = stop_event or threading.Event()
        self.platform = platform_adapter or get_platform_adapter()
        self.logger = get_logger()
        self.policy_resolver = PolicyResolver()

        self.current_resolved_policy: Optional[ResolvedPolicy] = None
        self.last_run_time: Optional[float] = None
        self.next_run_time: Optional[float] = None
        self._is_backup_running = False
        self._lock = threading.Lock()

        # Load local cached policy if available for restart recovery / offline resilience
        self._load_cached_policy()

    def _get_cache_path(self) -> str:
        return self.platform.get_policy_cache_path()

    def _load_cached_policy(self) -> None:
        """Load locally cached policy to survive server downtime or restart recovery."""
        cache_path = self._get_cache_path()
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    raw_policy = json.load(f)
                resolved = self.policy_resolver.resolve_policy(raw_policy)
                self.current_resolved_policy = resolved
                self.logger.info(f"Loaded cached policy '{resolved.policy_name}' from {cache_path}")
                self._calculate_next_run(raw_policy)
            except Exception as e:
                self.logger.warning(f"Could not parse local policy cache: {e}")

    def _save_cached_policy(self, raw_policy: Dict[str, Any]) -> None:
        """Persist authoritative server policy locally."""
        cache_path = self._get_cache_path()
        try:
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(raw_policy, f, indent=2)
            self.logger.debug(f"Saved local policy cache to {cache_path}")
        except Exception as e:
            self.logger.warning(f"Failed to write local policy cache: {e}")

    def _calculate_next_run(self, raw_policy: Dict[str, Any]) -> None:
        """Calculate next scheduled backup run time based on policy interval or RPO."""
        now = time.time()
        # Default schedule interval: policy schedule_interval_seconds or rpo_minutes (fallback 3600s)
        interval_seconds = raw_policy.get("schedule_interval_seconds")
        if not interval_seconds:
            rpo_mins = raw_policy.get("rpo_minutes") or raw_policy.get("schedule_interval_minutes")
            interval_seconds = (int(rpo_mins) * 60) if rpo_mins else 3600

        interval_seconds = max(60, int(interval_seconds))
        if self.last_run_time:
            self.next_run_time = self.last_run_time + interval_seconds
        else:
            self.next_run_time = now + interval_seconds

    def sync_policy_and_jobs(self) -> Optional[ResolvedPolicy]:
        """Fetch active policy and pending jobs from server, executing queued backups."""
        if not self.identity.client_id:
            self.logger.debug("Client not registered yet; skipping synchronization.")
            return None

        try:
            config_data = self.api_client.get_agent_config(self.identity.client_id)
            raw_policy = config_data.get("policy")
            if raw_policy:
                resolved = self.policy_resolver.resolve_policy(raw_policy)
                self.current_resolved_policy = resolved
                self._save_cached_policy(raw_policy)
                self._calculate_next_run(raw_policy)
                self.logger.debug(
                    f"Policy '{resolved.policy_name}' synchronized: "
                    f"{len(resolved.valid_paths)} valid targets."
                )
            else:
                self.logger.debug("No active backup policy assigned by server.")
                resolved = None

            # Check for server-triggered "Backup Now" / pending jobs
            pending_job = config_data.get("pending_job")
            if pending_job and resolved and resolved.valid_paths:
                b_type = (pending_job.get("backup_type") or "full").lower()
                self.logger.info(
                    f"Received server-triggered backup job #{pending_job.get('job_id')} "
                    f"({b_type.upper()}). Launching via common BackupEngine..."
                )
                self.execute_backup(b_type, source="server")

            return resolved
        except ApiClientError as e:
            self.logger.warning(f"Could not sync policy from control plane: {e}. Using cached policy if available.")
            return self.current_resolved_policy

    def execute_backup(self, backup_type: str = "full", source: str = "scheduler") -> Optional[Any]:
        """
        Unified Backup Engine execution point for BOTH scheduled triggers
        and server-triggered 'Backup Now' jobs.
        Enforces local mutual exclusion and active-job deduplication.
        """
        with self._lock:
            if self._is_backup_running:
                self.logger.warning(
                    f"Backup trigger from {source} skipped: Another backup is already active on this agent."
                )
                return None
            self._is_backup_running = True

        try:
            if not self.current_resolved_policy or not self.current_resolved_policy.valid_paths:
                self.logger.warning(f"Cannot execute {backup_type} backup: No valid paths in active policy.")
                return None

            self.logger.info(f"Starting {backup_type.upper()} backup [Trigger: {source.upper()}]...")
            engine = BackupEngine(
                config=self.config,
                identity=self.identity,
                api_client=self.api_client,
                max_workers=self.config.max_workers,
                platform_adapter=self.platform
            )

            if backup_type.lower() == "incremental":
                try:
                    summary = engine.run_incremental_backup(
                        self.current_resolved_policy,
                        stop_event=self.stop_event
                    )
                except Exception as inc_err:
                    self.logger.warning(f"Incremental backup failed ({inc_err}). Falling back to full baseline.")
                    summary = engine.run_full_backup(
                        self.current_resolved_policy,
                        stop_event=self.stop_event
                    )
            else:
                summary = engine.run_full_backup(
                    self.current_resolved_policy,
                    stop_event=self.stop_event
                )

            self.last_run_time = time.time()
            if self.current_resolved_policy:
                # Recalculate next run after completion
                self.next_run_time = self.last_run_time + 3600

            self.logger.info(
                f"Completed backup [Trigger: {source.upper()}]. "
                f"Status: {summary.status}, Duration: {summary.duration_seconds}s"
            )
            return summary

        finally:
            with self._lock:
                self._is_backup_running = False

    def trigger_full_backup(self) -> Optional[Any]:
        """Trigger an immediate full backup locally using current resolved policy."""
        if not self.current_resolved_policy:
            self.sync_policy_and_jobs()
        return self.execute_backup("full", source="manual")

    def run_loop(self) -> None:
        """
        Lightweight continuous agent scheduler loop:
        - Heartbeat and policy sync
        - Active-job detection
        - Scheduled trigger execution
        - Server-triggered 'Backup Now' reception
        """
        self.logger.info("Starting RetroVault Agent scheduler loop.")

        # Initial sync on startup
        self.sync_policy_and_jobs()

        poll_interval = getattr(self.config, "heartbeat_interval_seconds", 30)

        while not self.stop_event.is_set():
            if self.stop_event.wait(timeout=poll_interval):
                break

            # 1. Sync policy and check for queued server jobs
            self.sync_policy_and_jobs()

            # 2. Check scheduled trigger
            now = time.time()
            if self.next_run_time and now >= self.next_run_time:
                self.logger.info("Schedule window reached. Triggering automatic backup...")
                # Automatic: default to incremental if baseline exists
                self.execute_backup("incremental", source="scheduler")

        self.logger.info("RetroVault Agent scheduler stopped cleanly.")
