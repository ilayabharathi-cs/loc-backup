# RetroVault V11 Workload Providers Guide

## Provider Framework Overview
The workload provider subsystem abstracts application engines into a unified lifecycle:
`discover()` -> `pre_snapshot_hook()` -> `quiesce()` -> `snapshot_backup()` -> `unquiesce()` -> `post_snapshot_hook()` -> `verify_consistency()` -> `restore_preview()` -> `restore_workload()`.

## 1. Windows Filesystem Provider (`WINDOWS_FILESYSTEM`)
- **Capabilities**: VSS Volume Snapshot, USN Change Journal, granular file/folder restore.
- **Consistency State**: Produces `FILE_SYSTEM_CONSISTENT` (clean filesystem metadata and flushed NTFS buffers).
- **Fallback**: If VSS is disabled or fails, falls back to `CRASH_CONSISTENT`.
- **Status**: **SUPPORTED**

## 2. Microsoft SQL Server Provider (`MSSQL`)
- **Capabilities**: Instance and database enumeration, database inclusion/exclusion, recovery model identification (`SIMPLE`, `FULL`, `BULK_LOGGED`), VSS SQL Writer interaction, Full & Transaction Log backup workflows, and LSN chain tracking.
- **Credential Handling**: Integrates with the Secret Manager. Passwords are never hardcoded and are never emitted in API responses, logs, or telemetry.
- **Consistency State**: Produces `APPLICATION_CONSISTENT` when VSS SQL Writer generates confirmed LSN checkpoints and page checksums pass.
- **Diagnostics**: In unreachable scenarios, emits clear diagnostic errors (`INSTANCE_UNREACHABLE`, `AUTHENTICATION_FAILED`).
- **Status**: **SUPPORTED**

## 3. PostgreSQL Provider (`POSTGRESQL`)
- **Capabilities**: Database catalog enumeration, system database exclusion (`template0`, `template1`), MVCC transaction isolation snapshot, WAL LSN tracking, custom format dump, and SHA-256 integrity hashing.
- **Consistency State**: Produces `APPLICATION_CONSISTENT` when verified database dump and active transaction LSN are captured.
- **Status**: **SUPPORTED**

## 4. Generic Application Provider (`GENERIC_APP`)
- **Capabilities**: Administrator-defined hooks for `PRE_BACKUP`, `QUIESCE`, `SNAPSHOT`, `POST_BACKUP`, and `VALIDATE`.
- **Security Guardrails**:
  - Explicit allow-list of approved binaries (`echo`, `cmd.exe`, `powershell.exe`, `python`, `tar`, `gzip`, `mysqldump`, `pg_dump`).
  - Strict parameterization (`subprocess.run(tokens, shell=False)`).
  - Rejection of shell chaining and redirection operators (`;`, `&&`, `||`, `|`, `>`, `<`).
  - Output sanitization and credential masking.
  - Timeout enforcement (default 30s) and exit-code validation.
- **Consistency State**: If pre-hook fails or quiesce hook is absent, the system strictly assigns `FAILED` or `CRASH_CONSISTENT`—never `APPLICATION_CONSISTENT`.
- **Status**: **SUPPORTED**

## Capability Summary Table

| Provider | Quiesce / Freeze | Log Backup | PITR | Granular Restore | Status |
|---|---|---|---|---|---|
| WINDOWS_FILESYSTEM | VSS Shadow Copy | N/A | N/A | Supported | **SUPPORTED** |
| MSSQL | VSS SQL Writer | Supported | Supported | Supported | **SUPPORTED** |
| POSTGRESQL | MVCC Snapshot | Supported | Supported | Supported | **SUPPORTED** |
| GENERIC_APP | Custom Quiesce Hook | Degraded | Degraded | Supported | **SUPPORTED** |
