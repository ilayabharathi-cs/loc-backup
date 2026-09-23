"""Scheduler and backup orchestration foundation for RetroVault Agent."""

import time
import threading
from typing import Optional, Dict, Any
from agent.src.config import AgentConfig
from agent.src.identity import DeviceIdentity
from agent.src.api_client import BackendApiClient, ApiClientError
from agent.src.policy_resolver import PolicyResolver, ResolvedPolicy
from agent.src.logger import get_logger


class BackupScheduler:
    """Orchestrates periodic policy synchronization and backup execution hooks."""

    def __init__(
        self,
        config: AgentConfig,
        identity: DeviceIdentity,
        api_client: BackendApiClient,
        stop_event: Optional[threading.Event] = None
    ):
        self.config = config
        self.identity = identity
        self.api_client = api_client
        self.stop_event = stop_event or threading.Event()
        self.logger = get_logger()
        self.policy_resolver = PolicyResolver()
        self.current_resolved_policy: Optional[ResolvedPolicy] = None

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
                self.logger.debug(
                    f"Policy '{resolved.policy_name}' synchronized: "
                    f"{len(resolved.valid_paths)} valid targets."
                )
            else:
                self.logger.debug("No active backup policy assigned by server.")
                resolved = None

            # Check for queued/pending backup jobs
            pending_job = config_data.get("pending_job")
            if pending_job and resolved and resolved.valid_paths:
                b_type = (pending_job.get("backup_type") or "full").lower()
                self.logger.info(f"Received pending backup job: {pending_job.get('job_id')} ({b_type.upper()}). Initiating...")
                from agent.src.backup.backup_engine import BackupEngine
                engine = BackupEngine(self.config, self.identity, self.api_client)
                if b_type == "incremental":
                    summary = engine.run_incremental_backup(resolved, stop_event=self.stop_event)
                else:
                    summary = engine.run_full_backup(resolved, stop_event=self.stop_event)
                self.logger.info(f"Executed pending backup job ({b_type.upper()}). Status: {summary.status}")

            return resolved
        except ApiClientError as e:
            self.logger.warning(f"Could not sync policy from control plane: {e}")
            return None

    def trigger_full_backup(self) -> Optional[Any]:
        """Trigger an immediate full backup locally using current resolved policy."""
        if not self.current_resolved_policy:
            self.sync_policy_and_jobs()

        if self.current_resolved_policy:
            from agent.src.backup.backup_engine import BackupEngine
            engine = BackupEngine(self.config, self.identity, self.api_client)
            return engine.run_full_backup(self.current_resolved_policy, stop_event=self.stop_event)
        return None

    def run_loop(self) -> None:
        """Periodic scheduler loop synchronizing policy and evaluating backup triggers."""
        self.logger.info("Starting backup scheduler.")

        # Sync policy and check for queued jobs on startup
        self.sync_policy_and_jobs()

        # Poll every 30 seconds for queued jobs or policy changes
        poll_interval = 30
        while not self.stop_event.is_set():
            if self.stop_event.wait(timeout=poll_interval):
                break

            self.sync_policy_and_jobs()

        self.logger.info("Backup scheduler stopped cleanly.")
