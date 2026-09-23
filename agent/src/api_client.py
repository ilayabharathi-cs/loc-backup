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

    def get_latest_recovery_point(self, client_id: str, policy_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Fetch latest valid completed Recovery Point for baseline comparison."""
        endpoint = f"/backups/recovery-points/latest?client_id={client_id}"
        if policy_id is not None:
            endpoint += f"&policy_id={policy_id}"
        res = self._make_request("GET", endpoint)
        if res.get("success"):
            return res.get("data")
        return None

    def get_recovery_point_manifest(self, recovery_point_id: int, include_deleted: bool = False) -> Dict[str, Any]:
        """Fetch the logical file manifest of a Recovery Point."""
        endpoint = f"/backups/recovery-points/{recovery_point_id}/manifest"
        if include_deleted:
            endpoint += "?include_deleted=true"
        res = self._make_request("GET", endpoint)
        if res.get("success"):
            return res.get("data", {})
        raise ApiClientError(f"Failed to retrieve manifest for recovery point {recovery_point_id}: {res.get('error')}")

    def record_run_metadata(self, run_id: int, files: list) -> list:
        """Batch record UNCHANGED and DELETED file metadata on the server."""
        if not files:
            return []
        res = self._make_request("POST", f"/backups/runs/{run_id}/record-metadata", {"files": files})
        if res.get("success"):
            return res.get("data", [])
        raise ApiClientError(f"Failed to record run metadata for run {run_id}: {res.get('error')}")

    def create_upload_session(
        self,
        run_id: int,
        file_path: str,
        relative_path: Optional[str],
        total_size: int,
        chunk_size: int = 4194304,
        change_type: str = "FULL",
        expected_sha256: Optional[str] = None,
        file_mtime: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create or resume an upload session on the control plane."""
        payload = {
            "file_path": file_path,
            "relative_path": relative_path,
            "total_size": total_size,
            "chunk_size": chunk_size,
            "change_type": change_type,
            "expected_sha256": expected_sha256,
            "file_mtime": file_mtime
        }
        res = self._make_request("POST", f"/backups/runs/{run_id}/upload-session", payload)
        if res.get("success"):
            return res.get("data", {})
        raise ApiClientError(f"Failed to create upload session: {res.get('error') or res.get('message')}")

    def get_upload_session_status(self, session_id: str) -> Dict[str, Any]:
        """Query server for confirmed persisted chunks (Server Authority)."""
        res = self._make_request("GET", f"/backups/upload-session/{session_id}/status")
        if res.get("success"):
            return res.get("data", {})
        raise ApiClientError(f"Failed to get upload session status: {res.get('error') or res.get('message')}")

    def upload_chunk(
        self,
        session_id: str,
        chunk_index: int,
        chunk_bytes: bytes,
        chunk_sha256: str,
        offset: Optional[int] = None
    ) -> Dict[str, Any]:
        """Upload individual chunk with SHA-256 integrity verification and idempotency."""
        url = f"{self.base_url}/api/v1/backups/upload-session/{session_id}/chunks/{chunk_index}"
        headers = {
            "User-Agent": f"RetroVault-Agent/{self.config.agent_version}",
            "Content-Type": "application/octet-stream",
            "Content-Length": str(len(chunk_bytes)),
            "X-Chunk-SHA256": chunk_sha256
        }
        if offset is not None:
            headers["X-Chunk-Offset"] = str(offset)

        req = Request(url, data=chunk_bytes, headers=headers, method="PUT")
        with urlopen(req, timeout=self.timeout) as resp:
            body = resp.read().decode("utf-8")
            result = json.loads(body) if body else {}
            if result.get("success"):
                return result.get("data", {})
            raise ApiClientError(f"Chunk upload rejected: {result.get('error')}")

    def complete_upload_session(self, session_id: str, final_sha256: str, total_size: int) -> Dict[str, Any]:
        """Finalize upload session and verify file integrity on server."""
        payload = {
            "final_sha256": final_sha256,
            "total_size": total_size
        }
        res = self._make_request("POST", f"/backups/upload-session/{session_id}/complete", payload)
        if res.get("success"):
            return res.get("data", {})
        raise ApiClientError(f"Failed to complete upload session: {res.get('error') or res.get('message')}")

    def get_run_state(self, run_id: int) -> Dict[str, Any]:
        """Fetch current run state and lease status."""
        res = self._make_request("GET", f"/backups/runs/{run_id}/state")
        if res.get("success"):
            return res.get("data", {})
        raise ApiClientError(f"Failed to get run state: {res.get('error')}")

    def update_run_state(self, run_id: int, state: str, message: Optional[str] = None) -> Dict[str, Any]:
        """Report run state transition to server."""
        payload = {"state": state, "message": message}
        res = self._make_request("POST", f"/backups/runs/{run_id}/state", payload)
        if res.get("success"):
            return res.get("data", {})
        raise ApiClientError(f"Failed to update run state: {res.get('error')}")

    def save_run_checkpoint(self, run_id: int, checkpoint_data: Dict[str, Any]) -> Dict[str, Any]:
        """Sync local checkpoint to server."""
        res = self._make_request("POST", f"/backups/runs/{run_id}/checkpoint", checkpoint_data)
        if res.get("success"):
            return res.get("data", {})
        raise ApiClientError(f"Failed to record checkpoint on server: {res.get('error')}")

    def interrupt_run(self, run_id: int) -> Dict[str, Any]:
        """Mark run as INTERRUPTED on server."""
        res = self._make_request("POST", f"/backups/runs/{run_id}/interrupt")
        if res.get("success"):
            return res.get("data", {})
        raise ApiClientError(f"Failed to interrupt run: {res.get('error')}")

    def resume_run(self, run_id: int) -> Dict[str, Any]:
        """Resume an interrupted run."""
        res = self._make_request("POST", f"/backups/runs/{run_id}/resume")
        if res.get("success"):
            return res.get("data", {})
        raise ApiClientError(f"Failed to resume run: {res.get('error')}")

    def renew_run_lease(self, run_id: int, lease_id: str, duration_seconds: int = 300) -> Dict[str, Any]:
        """Renew backup run ownership lease."""
        payload = {"lease_id": lease_id, "duration_seconds": duration_seconds}
        res = self._make_request("POST", f"/backups/runs/{run_id}/lease/renew", payload)
        if res.get("success"):
            return res.get("data", {})
        raise ApiClientError(f"Failed to renew lease: {res.get('error')}")

