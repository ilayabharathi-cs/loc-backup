"""Startup recovery coordinator for RetroVault Agent V4."""

from typing import Optional, List, Dict, Any
from agent.src.config import AgentConfig
from agent.src.api_client import BackendApiClient, ApiClientError
from agent.src.backup.checkpoint_manager import CheckpointManager, BackupCheckpointData
from agent.src.logger import get_logger


class StartupRecoveryManager:
    """
    Evaluates local checkpoints on agent startup against server-authoritative state.
    Cleans obsolete checkpoints and prepares unfinished runs for resumption.
    """

    def __init__(self, config: AgentConfig, api_client: BackendApiClient, checkpoint_manager: CheckpointManager):
        self.config = config
        self.api_client = api_client
        self.checkpoint_manager = checkpoint_manager
        self.logger = get_logger()

    def scan_and_reconcile(self) -> Optional[BackupCheckpointData]:
        """
        Inspect local checkpoints, reconcile against server run state,
        and return the latest recoverable run checkpoint if eligible for resumption.
        """
        checkpoints = self.checkpoint_manager.list_checkpoints()
        if not checkpoints:
            self.logger.debug("Startup check: No local checkpoints found.")
            return None

        self.logger.info(f"Startup check: Discovered {len(checkpoints)} local checkpoint(s). Reconciling with server...")
        recoverable_candidate: Optional[BackupCheckpointData] = None

        for cp in checkpoints:
            try:
                server_state = self.api_client.get_run_state(cp.run_id)
                st = server_state.get("state", "").upper()
                status = server_state.get("status", "").lower()

                self.logger.info(f"Run #{cp.run_id} server state: state={st}, status={status}")

                if status == "completed" or st == "COMPLETED":
                    self.logger.info(f"Run #{cp.run_id} already completed on server. Cleaning local checkpoint.")
                    self.checkpoint_manager.clear_checkpoint(cp.run_id)
                elif status in ("failed", "cancelled") or st in ("FAILED", "CANCELLED"):
                    self.logger.info(f"Run #{cp.run_id} is {status} on server. Removing stale checkpoint.")
                    self.checkpoint_manager.clear_checkpoint(cp.run_id)
                elif st in ("INTERRUPTED", "BACKING_UP", "PAUSED", "RESUMING"):
                    self.logger.info(f"Run #{cp.run_id} is recoverable on server (state={st}).")
                    if self.config.resume_interrupted_runs:
                        if recoverable_candidate is None or cp.timestamp > recoverable_candidate.timestamp:
                            recoverable_candidate = cp
                else:
                    self.logger.warning(f"Run #{cp.run_id} in unhandled state '{st}'. Leaving checkpoint intact.")

            except ApiClientError as e:
                self.logger.warning(f"Could not verify Run #{cp.run_id} with server: {e}")
            except Exception as e:
                self.logger.error(f"Error reconciling checkpoint for Run #{cp.run_id}: {e}")

        return recoverable_candidate
