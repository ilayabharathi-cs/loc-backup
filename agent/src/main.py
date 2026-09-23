"""Main CLI entry point for RetroVault Universal Windows Backup Agent."""

import os
import sys
import json
import argparse
import signal

# Add repository root to sys.path so 'agent.src' package imports work cleanly
sys_path_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if sys_path_root not in sys.path:
    sys.path.insert(0, sys_path_root)

from agent.src.config import load_config
from agent.src.identity import DeviceIdentity
from agent.src.logger import setup_logger, get_logger
from agent.src.system_info import collect_system_info
from agent.src.user_discovery import discover_user_profiles
from agent.src.policy_resolver import PolicyResolver
from agent.src.api_client import BackendApiClient
from agent.src.heartbeat import HeartbeatWorker
from agent.src.service import RetroVaultAgentCore, PYWIN32_AVAILABLE

if PYWIN32_AVAILABLE:
    import win32serviceutil
    from agent.src.service import RetroVaultWindowsService


def cmd_sysinfo(args) -> None:
    """Print discovered system telemetry as formatted JSON."""
    identity = DeviceIdentity(args.identity)
    info = collect_system_info(identity.device_id)
    print(json.dumps(info, indent=2))


def cmd_resolve_policy(args) -> None:
    """Test policy resolution dynamically across discovered user profiles."""
    profiles = discover_user_profiles()
    resolver = PolicyResolver(profiles)

    sample_policy = {
        "id": 1,
        "name": "Standard Workstation Policy",
        "rpo_target_seconds": 120,
        "compression_enabled": True,
        "encryption_enabled": True,
        "include_paths": [
            "%USERPROFILE%\\Documents",
            "%USERPROFILE%\\Downloads",
            "%USERPROFILE%\\Pictures",
            "%USERPROFILE%\\Desktop",
            "%PROGRAMDATA%\\RetroVault",
            "D:\\CompanyData"  # Custom non-existent path to test safe handling
        ],
        "exclude_paths": [
            "%USERPROFILE%\\Downloads\\temp",
            "%TEMP%"
        ]
    }

    resolved = resolver.resolve_policy(sample_policy)
    print("\n--- Discovered User Profiles ---")
    for p in profiles:
        print(f"  User: {p.username} | Path: {p.profile_path} | SID: {p.sid}")

    print("\n--- Resolved Policy Summary ---")
    print(json.dumps(resolved.to_dict(), indent=2))


def cmd_register(args) -> None:
    """Perform one-time agent registration against backend."""
    config = load_config(args.config)
    setup_logger(config.log_level)
    logger = get_logger()

    identity = DeviceIdentity(args.identity)
    api_client = BackendApiClient(config)
    sys_info = collect_system_info(identity.device_id, config.agent_version)

    logger.info(f"Connecting to backend: {config.server_url}")
    try:
        data = api_client.register_agent(sys_info)
        client_id = data.get("client_id")
        if client_id:
            identity.set_registration(client_id)
            logger.info(f"Registration SUCCESS. Client ID: {client_id}, Device ID: {identity.device_id}")
            print(json.dumps(data, indent=2))
        else:
            logger.warning(f"Registration response missing client_id: {data}")
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        sys.exit(1)


def cmd_heartbeat_once(args) -> None:
    """Send a single heartbeat telemetry ping to backend."""
    config = load_config(args.config)
    setup_logger(config.log_level)
    logger = get_logger()

    identity = DeviceIdentity(args.identity)
    api_client = BackendApiClient(config)

    worker = HeartbeatWorker(config, identity, api_client)
    logger.info(f"Sending heartbeat to {config.server_url} for device {identity.device_id}...")
    success = worker.send_one()
    if success:
        logger.info("Heartbeat ping acknowledged successfully by backend control plane.")
    else:
        logger.error("Heartbeat ping failed.")
        sys.exit(1)


def cmd_backup_now(args) -> None:
    """Trigger an immediate full backup run of the current active policy."""
    config = load_config(args.config)
    setup_logger(config.log_level)
    logger = get_logger()

    identity = DeviceIdentity(args.identity)
    api_client = BackendApiClient(config)

    # 1. Ensure registered
    if not identity.client_id:
        logger.info("Agent not registered; performing enrollment before backup...")
        sys_info = collect_system_info(identity.device_id, config.agent_version)
        data = api_client.register_agent(sys_info)
        cid = data.get("client_id")
        if cid:
            identity.set_registration(cid)

    # 2. Fetch active policy from server
    logger.info("Fetching active policy from control plane...")
    try:
        config_data = api_client.get_agent_config(identity.client_id)
        raw_policy = config_data.get("policy")
    except Exception as e:
        logger.warning(f"Could not fetch policy from server: {e}. Falling back to default workstation policy.")
        raw_policy = None

    if not raw_policy:
        raw_policy = {
            "id": 1,
            "name": "Default Workstation Policy",
            "include_paths": ["%USERPROFILE%\\Documents", "%USERPROFILE%\\Desktop"],
            "exclude_paths": ["%TEMP%"]
        }

    # 3. Resolve policy
    resolver = PolicyResolver()
    resolved = resolver.resolve_policy(raw_policy)

    if not resolved.valid_paths:
        logger.error("No valid backup targets resolved from policy.")
        sys.exit(1)

    # 4. Execute Full Backup
    from agent.src.backup.backup_engine import BackupEngine
    engine = BackupEngine(config, identity, api_client)
    summary = engine.run_full_backup(resolved)

    print("\n--- Full Backup Execution Summary ---")
    print(json.dumps({
        "run_id": summary.run_id,
        "client_id": summary.client_id,
        "status": summary.status,
        "files_discovered": summary.files_discovered,
        "files_uploaded": summary.files_uploaded,
        "files_failed": summary.files_failed,
        "bytes_total": summary.bytes_total,
        "bytes_uploaded": summary.bytes_uploaded,
        "duration_seconds": summary.duration_seconds,
        "recovery_point_created": summary.recovery_point_created,
        "error_message": summary.error_message
    }, indent=2))


def cmd_incremental_backup(args) -> None:
    """Trigger an immediate incremental backup comparing against baseline Recovery Point."""
    config = load_config(args.config)
    setup_logger(config.log_level)
    logger = get_logger()

    identity = DeviceIdentity(args.identity)
    api_client = BackendApiClient(config)

    # 1. Ensure registered
    if not identity.client_id:
        logger.info("Agent not registered; performing enrollment before backup...")
        sys_info = collect_system_info(identity.device_id, config.agent_version)
        data = api_client.register_agent(sys_info)
        cid = data.get("client_id")
        if cid:
            identity.set_registration(cid)

    # 2. Fetch active policy from server
    logger.info("Fetching active policy from control plane...")
    try:
        config_data = api_client.get_agent_config(identity.client_id)
        raw_policy = config_data.get("policy")
    except Exception as e:
        logger.warning(f"Could not fetch policy from server: {e}. Falling back to default workstation policy.")
        raw_policy = None

    if not raw_policy:
        raw_policy = {
            "id": 1,
            "name": "Default Workstation Policy",
            "include_paths": ["%USERPROFILE%\\Documents", "%USERPROFILE%\\Desktop"],
            "exclude_paths": ["%TEMP%"]
        }

    # 3. Resolve policy
    resolver = PolicyResolver()
    resolved = resolver.resolve_policy(raw_policy)

    if not resolved.valid_paths:
        logger.error("No valid backup targets resolved from policy.")
        sys.exit(1)

    # 4. Check baseline pre-flight
    latest_rp = api_client.get_latest_recovery_point(identity.client_id, resolved.policy_id)
    if not latest_rp or not latest_rp.get("id"):
        err_msg = "No valid full backup baseline exists. Run a full backup first."
        logger.error(err_msg)
        print(f"Error: {err_msg}")
        sys.exit(1)

    # 5. Execute Incremental Backup
    from agent.src.backup.backup_engine import BackupEngine
    engine = BackupEngine(config, identity, api_client)
    try:
        summary = engine.run_incremental_backup(resolved)
    except ValueError as e:
        logger.error(str(e))
        print(f"Error: {e}")
        sys.exit(1)

    print("\n--- Incremental Backup Execution Summary ---")
    print(json.dumps({
        "run_id": summary.run_id,
        "client_id": summary.client_id,
        "backup_type": summary.backup_type,
        "status": summary.status,
        "files_discovered": summary.files_discovered,
        "files_uploaded": summary.files_uploaded,
        "files_failed": summary.files_failed,
        "files_new": summary.files_new,
        "files_modified": summary.files_modified,
        "files_unchanged": summary.files_unchanged,
        "files_deleted": summary.files_deleted,
        "bytes_total": summary.bytes_total,
        "bytes_uploaded": summary.bytes_uploaded,
        "duration_seconds": summary.duration_seconds,
        "recovery_point_created": summary.recovery_point_created,
        "error_message": summary.error_message
    }, indent=2))


def cmd_run(args) -> None:
    """Run agent daemon in foreground mode."""
    agent_core = RetroVaultAgentCore(args.config)

    def sig_handler(sig, frame):
        agent_core.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    agent_core.start()


def main():
    parser = argparse.ArgumentParser(
        description="RetroVault Universal Windows Backup Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("--config", type=str, default=None, help="Custom path to config.json")
    parser.add_argument("--identity", type=str, default=None, help="Custom path to identity.json")

    # Command modes
    parser.add_argument("--run", action="store_true", help="Run agent in foreground daemon mode")
    parser.add_argument("--register", action="store_true", help="Perform one-time agent registration and exit")
    parser.add_argument("--heartbeat-once", action="store_true", help="Perform one-time heartbeat telemetry ping and exit")
    parser.add_argument("--sysinfo", action="store_true", help="Print discovered dynamic system telemetry and exit")
    parser.add_argument("--resolve-policy", action="store_true", help="Resolve universal policy on this machine and exit")
    parser.add_argument("--backup-now", action="store_true", help="Trigger an immediate full file backup and display progress")
    parser.add_argument("--incremental-backup", action="store_true", help="Trigger an incremental backup comparing against latest baseline recovery point")
    parser.add_argument("--install-service", action="store_true", help="Install Windows Service via pywin32")
    parser.add_argument("--uninstall-service", action="store_true", help="Uninstall Windows Service via pywin32")

    args = parser.parse_args()

    if args.sysinfo:
        cmd_sysinfo(args)
    elif args.resolve_policy:
        cmd_resolve_policy(args)
    elif args.backup_now:
        cmd_backup_now(args)
    elif args.incremental_backup:
        cmd_incremental_backup(args)
    elif args.register:
        cmd_register(args)
    elif args.heartbeat_once:
        cmd_heartbeat_once(args)
    elif args.install_service:
        if PYWIN32_AVAILABLE:
            win32serviceutil.HandleCommandLine(RetroVaultWindowsService, argv=[sys.argv[0], "install"])
        else:
            print("pywin32 is not installed. Use scripts\\install_service.ps1 to register the Windows Service.")
    elif args.uninstall_service:
        if PYWIN32_AVAILABLE:
            win32serviceutil.HandleCommandLine(RetroVaultWindowsService, argv=[sys.argv[0], "remove"])
        else:
            print("pywin32 is not installed. Use scripts\\uninstall_service.ps1 to remove the Windows Service.")
    elif args.run or len(sys.argv) == 1:
        cmd_run(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
