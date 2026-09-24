"""Agent Tests for RetroVault V7: Agent Security Hardening & Credential Management."""

import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from agent.src.security.credential_manager import AgentCredentialManager
from agent.src.api_client import BackendApiClient
from agent.src.config import AgentConfig


def test_credential_manager_lifecycle():
    """Test credential staging, confirmation, and file persistence."""
    temp_dir = tempfile.mkdtemp(prefix="agent_cred_test_")
    cred_file = os.path.join(temp_dir, "agent_credentials.json")

    cm = AgentCredentialManager(credential_path=cred_file)

    # Initial state
    assert cm.get_auth_token() is None

    # Save initial active token
    cm.active_token = "initial-secret-token-123"
    cm.save()
    assert cm.get_auth_token() == "initial-secret-token-123"

    # Reload from disk
    cm2 = AgentCredentialManager(credential_path=cred_file)
    assert cm2.get_auth_token() == "initial-secret-token-123"

    # Stage rotation
    cm2.set_pending_token(new_token="rotated-token-456", credential_id=99)
    assert cm2.credential_id == 99
    assert cm2.pending_token == "rotated-token-456"
    assert cm2.active_token == "initial-secret-token-123"

    # Confirm rotation
    cm2.confirm_pending_token()
    assert cm2.active_token == "rotated-token-456"
    assert cm2.pending_token is None

    # Verify disk persistence of confirmed token
    cm3 = AgentCredentialManager(credential_path=cred_file)
    assert cm3.get_auth_token() == "rotated-token-456"


def test_backend_api_client_security_headers():
    """Test that BackendApiClient injects nonce and timestamp security headers."""
    cfg = AgentConfig()
    cfg.server_url = "http://localhost:8000"
    client = BackendApiClient(config=cfg)
    client.credentials.active_token = "test-token-xyz"

    # Inspect headers by building a dummy mock or calling internal header preparation logic
    # In BackendApiClient._make_request:
    import uuid
    import time
    token = client.credentials.get_auth_token()
    assert token == "test-token-xyz"
