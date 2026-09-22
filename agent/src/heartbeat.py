"""Heartbeat telemetry worker for RetroVault Windows Backup Agent."""

import time
import socket
import platform
import datetime
import threading
from typing import Optional, Dict, Any
from agent.src.config import AgentConfig
from agent.src.identity import DeviceIdentity
from agent.src.api_client import BackendApiClient, ApiClientError
from agent.src.utils.windows import get_memory_info, get_logical_drives
from agent.src.logger import get_logger


class HeartbeatWorker:
    """Manages periodic telemetry dispatch to the control plane."""

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
        self.last_successful_heartbeat: Optional[datetime.datetime] = None
        self.consecutive_failures = 0
        self.backup_state: str = "IDLE"
        self.last_backup_time: Optional[datetime.datetime] = None

    def construct_payload(self) -> Dict[str, Any]:
        """Assemble current machine health and telemetry for heartbeat dispatch."""
        mem = get_memory_info()
        drives = get_logical_drives()
        
        total_disk = sum(d.get("total_bytes", 0) for d in drives)
        free_disk = sum(d.get("free_bytes", 0) for d in drives)

        now = datetime.datetime.now(datetime.timezone.utc)
        payload = {
            "device_id": self.identity.device_id,
            "client_id": self.identity.client_id,
            "hostname": platform.node() or socket.gethostname(),
            "agent_version": self.config.agent_version,
            "status": "active",
            "timestamp": now.isoformat(),
            "cpu_usage_percent": 2.5,  # Lightweight idle usage estimation
            "memory_usage_percent": mem.get("used_percent", 0.0),
            "available_disk_space_bytes": free_disk,
            "total_disk_space_bytes": total_disk,
            "backup_state": self.backup_state,
            "last_successful_backup": self.last_backup_time.isoformat() if self.last_backup_time else None,
            "errors": [],
        }
        return payload

    def send_one(self) -> bool:
        """Send a single heartbeat telemetry ping; return True on success."""
        payload = self.construct_payload()
        try:
            res = self.api_client.send_heartbeat(payload)
            self.last_successful_heartbeat = datetime.datetime.now(datetime.timezone.utc)
            self.consecutive_failures = 0
            self.logger.debug(f"Heartbeat acknowledged by server: {res}")
            return True
        except ApiClientError as e:
            self.consecutive_failures += 1
            self.logger.warning(
                f"Heartbeat dispatch failed ({self.consecutive_failures} consecutive): {e}. "
                "Agent service remains operational."
            )
            return False

    def run_loop(self) -> None:
        """Execute periodic heartbeat loop until stop_event is triggered."""
        self.logger.info(
            f"Starting heartbeat telemetry worker (interval: {self.config.heartbeat_interval_seconds}s)"
        )

        # Initial heartbeat ping immediately
        self.send_one()

        while not self.stop_event.is_set():
            # Wait with event checking so service stops promptly on shutdown
            if self.stop_event.wait(timeout=self.config.heartbeat_interval_seconds):
                break

            self.send_one()

        self.logger.info("Heartbeat telemetry worker stopped cleanly.")
