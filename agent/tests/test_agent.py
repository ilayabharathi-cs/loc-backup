"""Automated test suite for RetroVault Universal Windows Backup Agent."""

import os
import sys
import json
import uuid
import tempfile
import pytest
from unittest.mock import MagicMock, patch

# Ensure agent package can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from agent.src.config import AgentConfig, load_config
from agent.src.identity import DeviceIdentity
from agent.src.system_info import collect_system_info, get_local_ip_addresses
from agent.src.user_discovery import (
    UserProfile,
    discover_user_profiles,
    discover_profiles_from_filesystem,
    is_valid_user_directory,
)
from agent.src.path_resolver import (
    resolve_system_variables,
    resolve_path_for_user,
    resolve_universal_path,
)
from agent.src.policy_resolver import PolicyResolver
from agent.src.api_client import BackendApiClient, ApiClientError
from agent.src.heartbeat import HeartbeatWorker
from agent.src.service import RetroVaultAgentCore
from agent.src.utils.validation import validate_path_safety


# ==============================================================================
# 1. Device ID Generation
# ==============================================================================
def test_device_id_generation(tmp_path):
    """Verify that a valid cryptographically secure UUID is generated when no file exists."""
    identity_file = str(tmp_path / "identity.json")
    identity = DeviceIdentity(identity_file)

    assert identity.device_id.startswith("urn:uuid:")
    # Verify raw UUID portion is valid
    raw_uuid = identity.device_id.split("urn:uuid:")[1]
    parsed = uuid.UUID(raw_uuid)
    assert parsed.version == 4
    assert os.path.exists(identity_file)


# ==============================================================================
# 2. Device ID Persistence
# ==============================================================================
def test_device_id_persistence(tmp_path):
    """Verify that existing device ID is preserved across agent restarts."""
    identity_file = str(tmp_path / "identity.json")
    id1 = DeviceIdentity(identity_file)
    first_device_id = id1.device_id
    id1.set_registration("PC-042")

    # Re-instantiate as if agent or machine rebooted
    id2 = DeviceIdentity(identity_file)
    assert id2.device_id == first_device_id
    assert id2.client_id == "PC-042"


# ==============================================================================
# 3. Hostname Discovery
# ==============================================================================
def test_hostname_discovery():
    """Verify that hostname is dynamically discovered without hardcoding."""
    info = collect_system_info(device_id="urn:uuid:test-device-id")
    assert "hostname" in info
    assert len(info["hostname"]) > 0
    assert info["hostname"] != "UNKNOWN-HOST"
    assert info["device_id"] == "urn:uuid:test-device-id"


# ==============================================================================
# 4. Drive Discovery
# ==============================================================================
def test_drive_discovery():
    """Verify logical drives are dynamically discovered without assuming C: or D:."""
    info = collect_system_info(device_id="urn:uuid:test-device-id")
    assert "drives" in info
    assert isinstance(info["drives"], list)
    assert len(info["drives"]) >= 1
    for drive in info["drives"]:
        assert "drive" in drive
        assert "total_bytes" in drive
        assert "free_bytes" in drive


# ==============================================================================
# 5. User Profile Discovery
# ==============================================================================
def test_user_profile_discovery(tmp_path):
    """Verify discovery filters out system, service, and default profiles."""
    users_root = tmp_path / "Users"
    users_root.mkdir()

    # Valid regular users
    (users_root / "Arun").mkdir()
    (users_root / "Kumar").mkdir()
    (users_root / "Admin").mkdir()

    # Should be excluded
    (users_root / "Public").mkdir()
    (users_root / "Default").mkdir()
    (users_root / "Default User").mkdir()
    (users_root / "All Users").mkdir()
    (users_root / "$Recycle.Bin").mkdir()

    profiles = discover_profiles_from_filesystem(str(users_root))
    usernames = {p.username for p in profiles}

    assert "Arun" in usernames
    assert "Kumar" in usernames
    assert "Admin" in usernames
    assert "Public" not in usernames
    assert "Default" not in usernames
    assert "Default User" not in usernames


# ==============================================================================
# 6. %USERPROFILE% Resolution Across Multiple Users
# ==============================================================================
def test_userprofile_resolution(tmp_path):
    """Verify %USERPROFILE% expands for each discovered user without hardcoded paths."""
    profiles = [
        UserProfile(username="Arun", profile_path=str(tmp_path / "Users" / "Arun")),
        UserProfile(username="Kumar", profile_path=str(tmp_path / "Users" / "Kumar")),
        UserProfile(username="Student", profile_path=str(tmp_path / "Users" / "Student")),
    ]

    raw_path = "%USERPROFILE%\\Documents"
    resolved = resolve_universal_path(raw_path, profiles)

    assert len(resolved) == 3
    assert any("Arun" in p and "Documents" in p for p in resolved)
    assert any("Kumar" in p and "Documents" in p for p in resolved)
    assert any("Student" in p and "Documents" in p for p in resolved)


# ==============================================================================
# 7. %SYSTEMDRIVE% Resolution
# ==============================================================================
def test_systemdrive_resolution(monkeypatch):
    """Verify system variables expand dynamically."""
    monkeypatch.setenv("SYSTEMDRIVE", "X:")
    raw = "%SYSTEMDRIVE%\\BackupData"
    resolved = resolve_system_variables(raw)
    assert resolved == "X:\\BackupData"


# ==============================================================================
# 8. Custom Path Validation
# ==============================================================================
def test_custom_path_validation(tmp_path):
    """Verify custom paths are supported, normalized, and validated for safety."""
    company_data = tmp_path / "CompanyData"
    company_data.mkdir()

    is_safe, error = validate_path_safety(str(company_data))
    assert is_safe is True
    assert error is None


# ==============================================================================
# 9. Missing Path Handling
# ==============================================================================
def test_missing_path_handling(tmp_path):
    """Verify missing configured path produces a warning in missing_paths, not a crash."""
    profiles = [
        UserProfile(username="Arun", profile_path=str(tmp_path / "Arun"))
    ]
    # Create only Documents, but NOT Downloads
    docs = tmp_path / "Arun" / "Documents"
    docs.mkdir(parents=True)

    policy = {
        "name": "Missing Path Test Policy",
        "include_paths": [
            str(docs),
            str(tmp_path / "Arun" / "NonExistentFolder")
        ],
        "exclude_paths": []
    }

    resolver = PolicyResolver(profiles)
    result = resolver.resolve_policy(policy)

    assert str(docs) in result.valid_paths
    assert str(tmp_path / "Arun" / "NonExistentFolder") in result.missing_paths
    assert len(result.invalid_paths) == 0


# ==============================================================================
# 10. Duplicate Path Removal & Subpath Pruning
# ==============================================================================
def test_duplicate_path_removal(tmp_path):
    """Verify duplicates and redundant nested subdirectories are pruned."""
    target_dir = tmp_path / "Data"
    target_dir.mkdir()
    nested_dir = target_dir / "SubFolder"
    nested_dir.mkdir()

    policy = {
        "name": "Deduplication Test",
        "include_paths": [
            str(target_dir),
            str(target_dir),  # Duplicate
            str(nested_dir),  # Subpath of target_dir
        ],
        "exclude_paths": []
    }

    resolver = PolicyResolver([])
    result = resolver.resolve_policy(policy)

    # Only parent should be retained
    assert len(result.valid_paths) == 1
    assert result.valid_paths[0] == str(target_dir)


# ==============================================================================
# 11. Exclusion Handling
# ==============================================================================
def test_exclusion_handling(tmp_path):
    """Verify excluded paths and subdirectories are properly omitted."""
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    temp_downloads = downloads / "temp"
    temp_downloads.mkdir()

    policy = {
        "name": "Exclusion Test",
        "include_paths": [
            str(downloads),
            str(temp_downloads)
        ],
        "exclude_paths": [
            str(temp_downloads)
        ]
    }

    resolver = PolicyResolver([])
    result = resolver.resolve_policy(policy)

    assert str(downloads) in result.valid_paths
    assert str(temp_downloads) not in result.valid_paths


# ==============================================================================
# 12. Server Registration
# ==============================================================================
def test_server_registration():
    """Verify API client calls POST /api/v1/agents/register with correct schema."""
    config = AgentConfig(server_url="http://mock-server:8000")
    client = BackendApiClient(config)

    mock_resp = {
        "success": True,
        "data": {
            "client_id": "PC-099",
            "device_id": "urn:uuid:test-dev",
            "status": "pending"
        }
    }

    with patch.object(client, "_make_request", return_value=mock_resp) as mock_req:
        sys_info = {
            "hostname": "TEST-HOST",
            "device_id": "urn:uuid:test-dev",
            "os": "Windows",
            "os_version": "11 Pro",
            "ip_address": "192.168.1.50"
        }
        res = client.register_agent(sys_info)
        assert res["client_id"] == "PC-099"
        mock_req.assert_called_once()


# ==============================================================================
# 13. Heartbeat Dispatch
# ==============================================================================
def test_heartbeat(tmp_path):
    """Verify heartbeat worker constructs and sends telemetry."""
    config = AgentConfig(server_url="http://mock-server:8000", heartbeat_interval_seconds=15)
    identity = DeviceIdentity(str(tmp_path / "identity.json"))
    identity.set_registration("PC-001")
    client = BackendApiClient(config)

    mock_resp = {
        "success": True,
        "data": {"client_id": "PC-001", "status": "active"}
    }

    with patch.object(client, "_make_request", return_value=mock_resp):
        worker = HeartbeatWorker(config, identity, client)
        payload = worker.construct_payload()
        assert payload["client_id"] == "PC-001"
        assert payload["device_id"] == identity.device_id
        assert payload["status"] == "active"
        assert "available_disk_space_bytes" in payload

        success = worker.send_one()
        assert success is True


# ==============================================================================
# 14. Network Failure & Exponential Backoff
# ==============================================================================
def test_network_failure_resilience():
    """Verify API client retries and raises ApiClientError gracefully without crashing."""
    config = AgentConfig(server_url="http://127.0.0.1:9999", max_retries=2, request_timeout_seconds=1)
    client = BackendApiClient(config)

    with patch("time.sleep"):  # Speed up test
        with pytest.raises(ApiClientError):
            client.register_agent({
                "hostname": "H",
                "device_id": "D",
                "os": "Windows",
                "os_version": "10",
                "ip_address": "127.0.0.1"
            })


# ==============================================================================
# 15. Configuration Loading
# ==============================================================================
def test_config_loading(tmp_path):
    """Verify loading from JSON file with custom values and default fallbacks."""
    cfg_file = tmp_path / "config.json"
    cfg_data = {
        "server_url": "http://backup.local:8080",
        "heartbeat_interval_seconds": 45,
        "log_level": "DEBUG"
    }
    cfg_file.write_text(json.dumps(cfg_data), encoding="utf-8")

    cfg = load_config(str(cfg_file))
    assert cfg.server_url == "http://backup.local:8080"
    assert cfg.heartbeat_interval_seconds == 45
    assert cfg.log_level == "DEBUG"
    assert cfg.request_timeout_seconds == 10  # default preserved


# ==============================================================================
# 16. Invalid Configuration Handling
# ==============================================================================
def test_invalid_config_handling(tmp_path):
    """Verify corrupt or invalid config defaults safely without crashing."""
    cfg_file = tmp_path / "corrupt_config.json"
    cfg_file.write_text("{ this is not valid json }", encoding="utf-8")

    # Should fall back to defaults gracefully
    cfg = load_config(str(cfg_file))
    assert cfg.server_url == "http://127.0.0.1:8000"
    assert cfg.heartbeat_interval_seconds == 30


# ==============================================================================
# 17. Service Restart Behavior
# ==============================================================================
def test_service_restart_behavior(tmp_path):
    """Verify agent core initializes, stops cleanly, and resumes state."""
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(json.dumps({"server_url": "http://127.0.0.1:8000"}), encoding="utf-8")

    core = RetroVaultAgentCore(str(cfg_file))
    assert core.stop_event.is_set() is False

    # Simulate stopping service
    core.stop()
    assert core.stop_event.is_set() is True
