"""HTTP API Client for communication between RetroVault Agent and Backend Control Plane."""

import time
import json
import random
from typing import Dict, Any, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from agent.src.config import AgentConfig
from agent.src.logger import get_logger


class ApiClientError(Exception):
    """Exception raised when API requests fail after retries."""
    pass


class BackendApiClient:
    """Client for RetroVault control plane REST API with exponential backoff retry."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.base_url = config.server_url.rstrip("/")
        self.timeout = config.request_timeout_seconds
        self.max_retries = config.max_retries
        self.logger = get_logger()

    def _make_request(self, method: str, endpoint: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Perform HTTP request with retry and exponential backoff."""
        url = f"{self.base_url}/api/v1{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"RetroVault-Agent/{self.config.agent_version}",
        }

        data_bytes = None
        if payload is not None:
            data_bytes = json.dumps(payload).encode("utf-8")

        attempt = 0
        backoff = 1.0

        while attempt < self.max_retries:
            attempt += 1
            try:
                req = Request(url, data=data_bytes, headers=headers, method=method)
                with urlopen(req, timeout=self.timeout) as resp:
                    resp_body = resp.read().decode("utf-8")
                    result = json.loads(resp_body) if resp_body else {}
                    return result
            except HTTPError as e:
                err_body = ""
                try:
                    err_body = e.read().decode("utf-8")
                except Exception:
                    pass

                self.logger.warning(
                    f"HTTP {e.code} on {method} {endpoint} (attempt {attempt}/{self.max_retries}): {err_body}"
                )
                # Client errors (400, 404, 422) should not loop indefinitely if permanent
                if e.code in (400, 404, 422) and attempt >= 2:
                    raise ApiClientError(f"HTTP {e.code}: {err_body}")

            except (URLError, TimeoutError, ConnectionError, OSError) as e:
                self.logger.warning(
                    f"Connection failure on {method} {endpoint} (attempt {attempt}/{self.max_retries}): {e}"
                )

            if attempt < self.max_retries:
                # Exponential backoff with random jitter (0.1 to 0.5s)
                sleep_time = backoff + random.uniform(0.1, 0.5)
                time.sleep(sleep_time)
                backoff = min(backoff * 2.0, 30.0)

        raise ApiClientError(f"Failed to communicate with {url} after {self.max_retries} attempts.")

    def register_agent(self, sys_info: Dict[str, Any]) -> Dict[str, Any]:
        """Register agent with the backend via POST /api/v1/agents/register."""
        payload = {
            "hostname": sys_info["hostname"],
            "device_id": sys_info["device_id"],
            "os": sys_info["os"],
            "os_version": sys_info.get("os_version", "Windows"),
            "ip_address": sys_info["ip_address"],
            "agent_version": self.config.agent_version,
        }
        res = self._make_request("POST", "/agents/register", payload)
        if res.get("success"):
            return res.get("data", {})
        raise ApiClientError(f"Registration rejected: {res.get('error') or res.get('message')}")

    def send_heartbeat(self, telemetry: Dict[str, Any]) -> Dict[str, Any]:
        """Send agent heartbeat via POST /api/v1/agents/heartbeat."""
        res = self._make_request("POST", "/agents/heartbeat", telemetry)
        if res.get("success"):
            return res.get("data", {})
        raise ApiClientError(f"Heartbeat rejected: {res.get('error') or res.get('message')}")

    def get_agent_config(self, client_id: str) -> Dict[str, Any]:
        """Fetch client configuration and policy via GET /api/v1/agents/{client_id}/config."""
        res = self._make_request("GET", f"/agents/{client_id}/config")
        if res.get("success"):
            return res.get("data", {})
        raise ApiClientError(f"Failed to fetch config for {client_id}: {res.get('error')}")
