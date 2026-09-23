"""Crash-safe local checkpoint manager for RetroVault Agent V4."""

import os
import json
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from agent.src.config import AgentConfig
from agent.src.utils.windows import get_programdata_path
from agent.src.logger import get_logger


@dataclass
class BackupCheckpointData:
    run_id: int
    client_id: str
    policy_id: Optional[int]
    current_file: Optional[str]
    current_file_path: Optional[str]
    file_size: int
    source_mtime: Optional[float]
    change_type: str
    upload_session_id: Optional[str]
    upload_object_id: Optional[str]
    bytes_uploaded: int
    bytes_verified: int
    last_successful_chunk: int
    retry_count: int
    timestamp: float
    checkpoint_version: int
    state: str


class CheckpointManager:
    """
    Manages crash-safe disk checkpoints using temporary files, fsync, and atomic rename.
    Ensures state is never corrupted even during abrupt termination or power loss.
    """

    def __init__(self, config: AgentConfig, custom_state_dir: Optional[str] = None):
        self.config = config
        self.logger = get_logger()

        if custom_state_dir:
            self.state_dir = os.path.abspath(custom_state_dir)
        elif config.state_dir:
            self.state_dir = os.path.abspath(config.state_dir)
        else:
            prog_data = get_programdata_path()
            self.state_dir = os.path.join(prog_data, "RetroVault", "agent", "state")

        try:
            os.makedirs(self.state_dir, exist_ok=True)
        except Exception as e:
            # Fallback to local state directory if ProgramData inaccessible
            self.state_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "state"))
            os.makedirs(self.state_dir, exist_ok=True)
            self.logger.warning(f"Could not create standard state directory; falling back to {self.state_dir}: {e}")

    def _get_checkpoint_path(self, run_id: int) -> str:
        return os.path.join(self.state_dir, f"run_{run_id}.checkpoint.json")

    def save_checkpoint(self, data: BackupCheckpointData) -> str:
        """
        Atomically persist checkpoint:
        1. Write to temporary file in the same directory.
        2. Flush and fsync to ensure data reaches physical disk.
        3. Atomic os.replace onto final checkpoint file.
        """
        final_path = self._get_checkpoint_path(data.run_id)
        tmp_path = f"{final_path}.{os.getpid()}.tmp"

        payload = asdict(data)
        serialized = json.dumps(payload, indent=2)

        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(serialized)
                f.flush()
                os.fsync(f.fileno())

            os.replace(tmp_path, final_path)
            self.logger.debug(f"Saved crash-safe checkpoint v{data.checkpoint_version} for Run #{data.run_id}")
            return final_path
        except Exception as e:
            self.logger.error(f"Failed to persist checkpoint for Run #{data.run_id}: {e}")
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            raise

    def load_checkpoint(self, run_id: int) -> Optional[BackupCheckpointData]:
        """Load and deserialize checkpoint for a specific run."""
        path = self._get_checkpoint_path(run_id)
        if not os.path.exists(path):
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return BackupCheckpointData(**raw)
        except Exception as e:
            self.logger.warning(f"Failed to load checkpoint file '{path}': {e}")
            return None

    def list_checkpoints(self) -> List[BackupCheckpointData]:
        """Discover all active checkpoints on disk for crash recovery evaluation."""
        results = []
        if not os.path.exists(self.state_dir):
            return results

        try:
            for fname in os.listdir(self.state_dir):
                if fname.startswith("run_") and fname.endswith(".checkpoint.json"):
                    full_path = os.path.join(self.state_dir, fname)
                    try:
                        with open(full_path, "r", encoding="utf-8") as f:
                            raw = json.load(f)
                        results.append(BackupCheckpointData(**raw))
                    except Exception as e:
                        self.logger.warning(f"Corrupt checkpoint file '{fname}': {e}")
        except Exception as e:
            self.logger.error(f"Error scanning state directory '{self.state_dir}': {e}")

        return results

    def clear_checkpoint(self, run_id: int) -> None:
        """Remove checkpoint file after run completes or is cleanly cancelled."""
        path = self._get_checkpoint_path(run_id)
        if os.path.exists(path):
            try:
                os.remove(path)
                self.logger.info(f"Cleaned up checkpoint for Run #{run_id}")
            except OSError as e:
                self.logger.warning(f"Could not remove checkpoint '{path}': {e}")
