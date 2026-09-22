# Implementation Plan: Universal Windows Backup Agent

Create a production-grade, universal Windows Backup Agent for **RetroVault Backup** that runs across any supported Windows machine without code modification. The agent dynamically discovers its environment, user profiles, and storage drives; manages persistent cryptographic device identity; resolves server-defined universal policies; runs as a resilient Windows Service; and reports telemetry back to the backend control plane.

## User Review Required

> [!IMPORTANT]
> **Zero Machine-Specific Hardcoding**:
> The agent codebase and installer will contain NO hardcoded usernames, hostnames, client IDs, device IDs, or drive letters. Everything is dynamically discovered at runtime or assigned by the server control plane.

> [!NOTE]
> **Windows Service & Fallback Mechanism**:
> The agent will include a native Windows Service module (`service.py`) supporting both `win32serviceutil` (when installed via PyWin32) and a native Windows Service wrapper via PowerShell/SC (`New-Service`), plus a standalone background daemon runner (`--run`) so it can be deployed or tested immediately on any Windows machine without requiring external compiler dependencies.

---

## Proposed Changes

Grouped by component under `agent/`:

### 1. Agent Core Architecture (`agent/src/`)

#### [NEW] [config.py](file:///d:/Projects/NULL/loc-backup/agent/src/config.py)
- Defines `AgentConfig` schema using Pydantic v2.
- Reads configuration from `%PROGRAMDATA%\RetroVault\agent\config.json` with fallback to local `config.json` and environment variables (`RETROVAULT_*`).
- Validates settings: `server_url`, `heartbeat_interval_seconds` (default 30s), `log_level`, `request_timeout_seconds`, `max_retries`, `verify_ssl`.

#### [NEW] [identity.py](file:///d:/Projects/NULL/loc-backup/agent/src/identity.py)
- Manages persistent device identity under `%PROGRAMDATA%\RetroVault\agent\identity.json`.
- Idempotent: checks for existing identity file; if present, loads the existing `device_id` and cached `client_id`; if absent, generates a cryptographically random UUIDv4 and persists it atomically.
- Device ID remains completely stable across machine reboots and service restarts.

#### [NEW] [logger.py](file:///d:/Projects/NULL/loc-backup/agent/src/logger.py)
- Configures structured rotating file logging under `%PROGRAMDATA%\RetroVault\agent\logs\agent.log` (max 10MB, 5 backups) and console stream logging.
- Masks sensitive data (tokens, secrets).

#### [NEW] [utils/](file:///d:/Projects/NULL/loc-backup/agent/src/utils/)
- [windows.py](file:///d:/Projects/NULL/loc-backup/agent/src/utils/windows.py): Dynamic Windows environment inspection using Win32 Registry (`winreg`) and ctypes (`kernel32.dll` for drive strings, disk free space) with fallback to `shutil.disk_usage`.
- [filesystem.py](file:///d:/Projects/NULL/loc-backup/agent/src/utils/filesystem.py): Safe atomic file writes, path canonicalization, directory creation with permissions.
- [validation.py](file:///d:/Projects/NULL/loc-backup/agent/src/utils/validation.py): Directory traversal protection (`..`), system-critical path safeguards (`C:\Windows`, `$Recycle.Bin`, system volume info).

#### [NEW] [system_info.py](file:///d:/Projects/NULL/loc-backup/agent/src/system_info.py)
- Collects comprehensive system telemetry dynamically:
  - `hostname` (`platform.node()`)
  - `os` ("Windows") & `os_version` (`platform.version()`, `platform.win32_ver()`)
  - `architecture` (`platform.machine()`)
  - CPU information (core count, frequency, load estimation)
  - RAM metrics (total, available, used %)
  - Dynamic local IP addresses enumeration
  - Dynamic logical drive discovery (discovers C:, D:, E:, etc., capacity, free space, filesystem type)
  - Boot timestamp

#### [NEW] [user_discovery.py](file:///d:/Projects/NULL/loc-backup/agent/src/user_discovery.py)
- Discovers user profiles dynamically:
  - Queries Windows Registry `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList`.
  - Filters out well-known service accounts (`S-1-5-18` LocalSystem, `S-1-5-19` LocalService, `S-1-5-20` NetworkService).
  - Filters out system and shared directories (`Default`, `Default User`, `Public`, `All Users`).
  - Resolves standard personal folders for every discovered user: `Desktop`, `Documents`, `Downloads`, `Pictures`, `Videos`, `Music`.

#### [NEW] [path_resolver.py](file:///d:/Projects/NULL/loc-backup/agent/src/path_resolver.py)
- Resolves logical environment variables (`%USERPROFILE%`, `%SYSTEMDRIVE%`, `%PROGRAMDATA%`, `%TEMP%`, `%APPDATA%`, etc.).
- Multi-user support: expands `%USERPROFILE%` across all eligible discovered user profiles on the workstation.

#### [NEW] [policy_resolver.py](file:///d:/Projects/NULL/loc-backup/agent/src/policy_resolver.py)
- Implements the complete policy resolution pipeline:
  1. Parses server-provided `include_paths` and `exclude_paths`.
  2. Expands variables across all user profiles.
  3. Canonicalizes paths and strips duplicates.
  4. Filters out excluded paths and redundant nested paths.
  5. Verifies filesystem existence and accessibility.
  6. Gracefully handles missing custom paths (logs warning, reports missing status to server, never crashes).
  7. Returns validated, deduplicated targets for backup execution.

#### [NEW] [api_client.py](file:///d:/Projects/NULL/loc-backup/agent/src/api_client.py)
- HTTP REST client communicating with the backend `/api/v1/` endpoints.
- Implements exponential backoff, retry jitter, and timeout handling.
- Endpoints consumed:
  - `POST /api/v1/agents/register`
  - `POST /api/v1/agents/heartbeat`
  - `GET /api/v1/agents/{client_id}/config`

#### [NEW] [heartbeat.py](file:///d:/Projects/NULL/loc-backup/agent/src/heartbeat.py)
- Periodic background worker sending system health and backup status telemetry to the backend.
- Survives network disconnects gracefully; reconnects automatically when the server is reachable.

#### [NEW] [scheduler.py](file:///d:/Projects/NULL/loc-backup/agent/src/scheduler.py)
- Coordinates policy synchronization and backup job orchestration.
- Designed with modular hooks for future USN Journal, VSS, compression, and encryption engines.

#### [NEW] [service.py](file:///d:/Projects/NULL/loc-backup/agent/src/service.py) & [main.py](file:///d:/Projects/NULL/loc-backup/agent/src/main.py)
- Windows Service integration and CLI interface supporting:
  - `--run`: Run agent foreground daemon
  - `--register`: Perform one-time registration and exit
  - `--heartbeat-once`: Perform one-time heartbeat ping and exit
  - `--sysinfo`: Print discovered system telemetry as JSON
  - `--resolve-policy`: Test policy resolution for local machine
  - `--install-service`: Register Windows service
  - `--uninstall-service`: Remove Windows service

---

### 2. Deployment & Installation Scripts (`agent/scripts/`)

#### [NEW] [install_service.ps1](file:///d:/Projects/NULL/loc-backup/agent/scripts/install_service.ps1)
- Automated PowerShell installation script:
  - Creates `%PROGRAMDATA%\RetroVault\agent\` directory structure and sets permissions.
  - Installs default configuration (`config.json`).
  - Registers the Windows Service with auto-start (`Automatic`) and crash restart recovery actions.
  - Starts the service.

#### [NEW] [uninstall_service.ps1](file:///d:/Projects/NULL/loc-backup/agent/scripts/uninstall_service.ps1)
- Stops and unregisters the Windows Service cleanly.

#### [NEW] [run_agent.ps1](file:///d:/Projects/NULL/loc-backup/agent/scripts/run_agent.ps1)
- PowerShell runner script for development and standalone operation.

---

### 3. Backend Minor Telemetry Extension (`server/`)

#### [MODIFY] [server/app/schemas/client.py](file:///d:/Projects/NULL/loc-backup/server/app/schemas/client.py)
- Add optional telemetry fields to `AgentHeartbeatRequest` (`cpu_usage_percent`, `memory_usage_percent`, `available_disk_space_bytes`, `backup_state`, `errors`) with `extra="ignore"` so the backend can receive rich telemetry while remaining backwards-compatible.

---

### 4. Automated Test Suite (`agent/tests/`)

#### [NEW] [test_agent.py](file:///d:/Projects/NULL/loc-backup/agent/tests/test_agent.py)
Mocked, isolated test suite covering all 17 required scenarios:
1. `test_device_id_generation`: generates valid UUIDv4.
2. `test_device_id_persistence`: loads existing device ID without regenerating.
3. `test_hostname_discovery`: dynamic hostname collection.
4. `test_drive_discovery`: enumerates drives without hardcoded C: or D:.
5. `test_user_profile_discovery`: finds users, skips system/service/public.
6. `test_userprofile_resolution`: resolves `%USERPROFILE%\Documents` across multiple simulated profiles.
7. `test_systemdrive_resolution`: expands `%SYSTEMDRIVE%` dynamically.
8. `test_custom_path_validation`: accepts valid custom paths.
9. `test_missing_path_handling`: logs warning, flags missing, does not crash.
10. `test_duplicate_path_removal`: deduplicates duplicate and nested paths.
11. `test_exclusion_handling`: filters out excluded paths.
12. `test_server_registration`: registers via API client and receives client ID.
13. `test_heartbeat`: constructs and dispatches heartbeat payload.
14. `test_network_failure_resilience`: retries with exponential backoff on connection errors.
15. `test_config_loading`: loads config from file and applies defaults.
16. `test_invalid_config_handling`: detects and handles corrupt/invalid config.
17. `test_service_restart_behavior`: restores state cleanly after restart.

---

## Verification Plan

### Automated Tests
1. **Agent Test Suite**:
   ```powershell
   .\server\.venv\Scripts\python.exe -m pytest agent/tests/test_agent.py -v
   ```
2. **Backend Regression Test Suite**:
   ```powershell
   .\server\.venv\Scripts\python.exe -m pytest server/tests/test_api.py -v
   ```
3. **Frontend Production Build**:
   ```powershell
   npm run build
   ```

### Live End-to-End Verification
1. Run `agent/src/main.py --sysinfo` to verify real dynamic system discovery on the host.
2. Run `agent/src/main.py --resolve-policy` to verify real user profile and path resolution.
3. Run `agent/src/main.py --register` against the live backend on `http://127.0.0.1:8000` to verify live registration and client ID assignment in the database.
4. Run `agent/src/main.py --heartbeat-once` to verify live heartbeat acknowledgment.
5. Verify updated client status and audit log in the live RetroVault web dashboard.
