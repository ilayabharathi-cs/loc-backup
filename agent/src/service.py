"""Windows Service module for RetroVault Backup Agent."""

import os
import sys
import time
import signal
import threading
from typing import Optional

from agent.src.config import load_config, AgentConfig
from agent.src.identity import DeviceIdentity
from agent.src.logger import setup_logger, get_logger
from agent.src.system_info import collect_system_info
from agent.src.api_client import BackendApiClient, ApiClientError
from agent.src.heartbeat import HeartbeatWorker
from agent.src.scheduler import BackupScheduler

# Windows Service imports (optional pywin32 support)
try:
    import win32serviceutil
    import win32service
    import win32event
    import servicemanager
    PYWIN32_AVAILABLE = True
except ImportError:
    PYWIN32_AVAILABLE = False


class RetroVaultAgentCore:
    """Core daemon engine managing threads, registration, and graceful shutdown."""

    def __init__(self, config_path: Optional[str] = None):
        self.config = load_config(config_path)
        self.logger = setup_logger(self.config.log_level)
        self.identity = DeviceIdentity()
        self.api_client = BackendApiClient(self.config)
        self.stop_event = threading.Event()
        self.threads = []

    def perform_registration(self) -> bool:
        """Register agent with backend if not already registered or to refresh details."""
        sys_info = collect_system_info(self.identity.device_id, self.config.agent_version)
        try:
            self.logger.info(
                f"Registering agent: Hostname='{sys_info['hostname']}', DeviceID='{self.identity.device_id}'"
            )
            data = self.api_client.register_agent(sys_info)
            client_id = data.get("client_id")
            if client_id:
                self.identity.set_registration(client_id)
                self.logger.info(f"Agent registration verified. Assigned client_id: {client_id}")
                return True
        except ApiClientError as e:
            self.logger.warning(
                f"Registration failed on startup: {e}. "
                "Agent will continue running and retry during regular operations."
            )
        return False

    def start(self) -> None:
        """Start agent background workers and block until stop_event is triggered."""
        self.logger.info("=" * 60)
        self.logger.info(f"Starting RetroVault Backup Agent v{self.config.agent_version}")
        self.logger.info(f"Persistent Device ID: {self.identity.device_id}")
        self.logger.info(f"Server URL: {self.config.server_url}")
        self.logger.info("=" * 60)

        # 1. Initial registration
        self.perform_registration()

        # 2. Start Heartbeat worker thread
        heartbeat_worker = HeartbeatWorker(
            config=self.config,
            identity=self.identity,
            api_client=self.api_client,
            stop_event=self.stop_event
        )
        t_heartbeat = threading.Thread(
            target=heartbeat_worker.run_loop,
            name="HeartbeatWorkerThread",
            daemon=True
        )
        t_heartbeat.start()
        self.threads.append(t_heartbeat)

        # 3. Start Scheduler worker thread
        scheduler = BackupScheduler(
            config=self.config,
            identity=self.identity,
            api_client=self.api_client,
            stop_event=self.stop_event
        )
        t_scheduler = threading.Thread(
            target=scheduler.run_loop,
            name="BackupSchedulerThread",
            daemon=True
        )
        t_scheduler.start()
        self.threads.append(t_scheduler)

        self.logger.info("RetroVault Backup Agent is active and running.")

        # Keep main thread alive until stopped
        try:
            while not self.stop_event.is_set():
                time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            self.stop()

    def stop(self) -> None:
        """Signal all threads to stop and wait for clean shutdown."""
        self.logger.info("Shutting down RetroVault Backup Agent...")
        self.stop_event.set()
        for t in self.threads:
            t.join(timeout=3.0)
        self.logger.info("RetroVault Backup Agent stopped cleanly.")


if PYWIN32_AVAILABLE:
    class RetroVaultWindowsService(win32serviceutil.ServiceFramework):
        _svc_name_ = "RetroVaultAgent"
        _svc_display_name_ = "RetroVault Backup Agent"
        _svc_description_ = "Continuous, enterprise-grade universal local backup agent for RetroVault."

        def __init__(self, args):
            super().__init__(args)
            self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
            self.agent_core = RetroVaultAgentCore()

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            self.agent_core.stop()
            win32event.SetEvent(self.hWaitStop)

        def SvcDoRun(self):
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, "")
            )
            # Run agent core in a daemon thread so SvcStop can set event promptly
            thread = threading.Thread(target=self.agent_core.start, daemon=True)
            thread.start()
            win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)
