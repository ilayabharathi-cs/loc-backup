"""Unit tests for RetroVault Agent Multi-Endpoint Failover (V9)."""

import pytest
from unittest.mock import patch, MagicMock
from urllib.error import URLError

from agent.src.config import AgentConfig
from agent.src.api_client import BackendApiClient, ApiClientError


def test_agent_multi_endpoint_failover():
    config = AgentConfig(
        server_url="http://node-a:8000",
        server_endpoints=["http://node-a:8000", "http://node-b:8000", "http://node-c:8000"],
        request_timeout_seconds=2,
        max_retries=3,
    )

    client = BackendApiClient(config)
    assert len(client.endpoints) == 3
    assert client.get_active_endpoint() == "http://node-a:8000"

    # Simulate node-a down (URLError), then node-b succeeds
    call_count = 0

    def mock_urlopen(req, timeout=None):
        nonlocal call_count
        call_count += 1
        url = req.full_url
        if "node-a:8000" in url:
            raise URLError("Connection refused: node-a offline")
        
        # node-b returns successful response
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"status": "ok", "node": "node-b"}'
        mock_resp.__enter__.return_value = mock_resp
        return mock_resp

    with patch("agent.src.api_client.urlopen", side_effect=mock_urlopen):
        res = client._make_request("GET", "/health")
        assert res["status"] == "ok"
        assert res["node"] == "node-b"
        # Client rotated to node-b
        assert client.get_active_endpoint() == "http://node-b:8000"
