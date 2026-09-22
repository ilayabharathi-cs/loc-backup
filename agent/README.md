# RetroVault Universal Windows Backup Agent

The **RetroVault Windows Backup Agent** is a production-grade, enterprise-ready background backup service engineered for Microsoft Windows workstations and servers.

---

## 1. Architectural Philosophy: Truly Universal

The agent codebase and installer contain **ZERO hardcoded**:
- Usernames (e.g. `Arun`, `Kumar`, `Admin`)
- Hostnames (e.g. `OFFICE-PC-01`)
- Client IDs (e.g. `PC-001`)
- Device IDs
- Drive letters (e.g. `C:\`, `D:\`)
- Absolute user profile paths (`C:\Users\...`)

The **SAME installer** and **SAME binary codebase** execute seamlessly across any Windows PC or Server without modification.

### Universal Path Resolution Example:
When the backup control plane defines a policy with:
```json
{
  "include_paths": [
    "%USERPROFILE%\\Documents",
    "%USERPROFILE%\\Downloads",
    "%USERPROFILE%\\Pictures"
  ],
  "exclude_paths": [
    "%USERPROFILE%\\Downloads\\temp",
    "%TEMP%"
  ]
}
```

The agent dynamically expands `%USERPROFILE%` across all legitimate, discovered user profiles on the target machine:
- **Workstation A** (Single user `Arun`):
  - `C:\Users\Arun\Documents`
  - `C:\Users\Arun\Downloads`
  - `C:\Users\Arun\Pictures`
- **Workstation B** (Multiple users `Kumar`, `Student`):
  - `C:\Users\Kumar\Documents`
  - `C:\Users\Kumar\Downloads`
  - `C:\Users\Student\Documents`
  - `C:\Users\Student\Downloads`

---

## 2. Directory & Component Structure

```text
agent/
├── src/
│   ├── main.py                  # CLI entry point (--run, --register, --sysinfo, etc.)
│   ├── service.py               # Windows Service and daemon lifecycle manager
│   ├── config.py                # External configuration loader and validator
│   ├── identity.py              # Persistent UUIDv4 device identity manager
│   ├── logger.py                # Rotating structured logger with credential masking
│   ├── system_info.py           # Dynamic hardware, OS, IP, and drive discovery
│   ├── user_discovery.py        # Windows Registry ProfileList and folder discovery
│   ├── path_resolver.py         # Universal environment and multi-user path expander
│   ├── policy_resolver.py       # Policy parsing, validation, deduplication, exclusions
│   ├── api_client.py            # HTTP REST client with exponential backoff retries
│   ├── heartbeat.py             # Periodic machine telemetry and health dispatch
│   ├── scheduler.py             # Policy synchronization and backup execution hooks
│   └── utils/
│       ├── windows.py           # Win32 APIs, ctypes, kernel32 drive discovery
│       ├── filesystem.py        # Atomic JSON writes and path normalization
│       └── validation.py        # Path traversal and system directory protection
├── scripts/
│   ├── install_service.ps1      # PowerShell script to register & start Windows Service
│   ├── uninstall_service.ps1    # PowerShell script to stop & unregister Windows Service
│   └── run_agent.ps1            # Development / standalone execution helper
├── tests/
│   └── test_agent.py            # Automated pytest suite covering 17 scenarios
├── config.example.json          # Sample configuration template
├── requirements.txt             # Agent dependencies
└── README.md
```

---

## 3. Persistent Device Identity

- Stored in `%PROGRAMDATA%\RetroVault\agent\identity.json`.
- Generated on initial startup as a cryptographically random UUIDv4 (`urn:uuid:<uuid>`).
- Persists across machine reboots, service restarts, and user logoffs.
- Caches server-assigned `client_id` upon enrollment.

---

## 4. Configuration

Stored in `%PROGRAMDATA%\RetroVault\agent\config.json`:
```json
{
  "server_url": "http://127.0.0.1:8000",
  "heartbeat_interval_seconds": 30,
  "log_level": "INFO",
  "request_timeout_seconds": 10,
  "max_retries": 5,
  "verify_ssl": true,
  "agent_version": "1.0.0"
}
```

---

## 5. Development & Testing Commands

### A. Run Automated Tests
```powershell
.\server\.venv\Scripts\python.exe -m pytest agent/tests/test_agent.py -v
```

### B. Discover Dynamic System Telemetry
```powershell
python agent/src/main.py --sysinfo
```

### C. Test Dynamic Policy Resolution
```powershell
python agent/src/main.py --resolve-policy
```

### D. Perform One-Time Agent Registration
```powershell
python agent/src/main.py --register
```

### E. Send One-Time Heartbeat Ping
```powershell
python agent/src/main.py --heartbeat-once
```

### F. Run Foreground Daemon
```powershell
python agent/src/main.py --run
```

---

## 6. Windows Service Installation & Management

Run the following commands in an **Administrator PowerShell** console:

### Install and Start Windows Service:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\agent\scripts\install_service.ps1 -ServerUrl "http://127.0.0.1:8000"
```

### Check Service Status:
```powershell
Get-Service -Name RetroVaultAgent
```

### View Live Agent Logs:
```powershell
Get-Content -Path "C:\ProgramData\RetroVault\agent\logs\agent.log" -Wait -Tail 30
```

### Stop and Uninstall Service:
```powershell
.\agent\scripts\uninstall_service.ps1
```
