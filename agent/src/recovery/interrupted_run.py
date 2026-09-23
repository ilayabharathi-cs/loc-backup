"""Graceful interruption and safe shutdown handler for RetroVault Agent V4."""

import os
import signal
import threading
from typing import Optional
from agent.src.api_client import BackendApiClient
from agent.src.backup.checkpoint_manager import CheckpointManager
from agent.src.windows.vss import VSSProvider
from agent.src.utils.lock import BackupLock
from agent.src.logger import get_logger


class InterruptedRunHandler:
    """Manages clean shutdown, lease release, and checkpoint flushing on shutdown."""

    def __init__(
        self,
        api_client: BackendApiClient,
        checkpoint_manager: CheckpointManager,
        vss_provider: Optional[VSSProvider] = None,
        backup_lock: Optional[BackupLock] = None
    ):
        self.api_client = api_client
        self.checkpoint_manager = checkpoint_manager
        self.vss_provider = vss_provider
        self.backup_lock = backup_lock
        self.logger = get_logger()
        self.stop_event = threading.Event()
        self.active_run_id: Optional[int] = None

    def set_active_run(self, run_id: Optional[int]) -> None:
        self.active_run_id = run_id

    def handle_shutdown(self, signum=None, frame=None) -> None:
        """Signal handler for graceful shutdown."""
        self.logger.info("Shutdown signal received. Initiating graceful shutdown...")
        self.stop_event.set()

        if self.active_run_id:
            try:
                self.logger.info(f"Marking Run #{self.active_run_id} as INTERRUPTED on control plane...")
                self.api_client.interrupt_run(self.active_run_id)
            except Exception as e:
                self.logger.warning(f"Could not report interruption to server: {e}")

        # Release VSS snapshots
        if self.vss_provider:
            try:
                self.vss_provider.release_snapshot()
            except Exception as e:
                self.logger.warning(f"Error releasing VSS snapshots: {e}")

        # Release local lock
        if self.backup_lock:
            try:
                self.backup_lock.release()
            except Exception as e:
                self.logger.warning(f"Error releasing backup lock: {e}")

        self.logger.info("Graceful shutdown cleanup complete.")
