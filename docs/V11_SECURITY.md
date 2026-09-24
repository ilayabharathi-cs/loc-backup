# RetroVault V11 Security Architecture & Safety Invariants

## Core Security Invariants
1. **No Hardcoded Credentials**: Database passwords and API keys are stored in Secret Manager and injected only into isolated runtime execution contexts.
2. **Credential Redaction in Logs & Telemetry**: Output filters automatically mask password fields (`password: [REDACTED]`) and truncate oversized command outputs.
3. **No Arbitrary Command Execution**: Workload hooks are restricted to an approved allow-list of executable binaries.
4. **Shell Injection Prevention**: All processes execute with `shell=False` and parameter tokenization. Chaining operators (`;`, `&&`, `||`, `|`, `>`, `<`) are rejected with `HTTP 403 / Exit Code 403`.
5. **No Autonomous Destructive Remediation**: Autonomous agents and workflows are strictly prohibited from:
   - Deleting Recovery Points (`DELETE_RECOVERY_POINT`).
   - Purging CAS storage objects (`PURGE_CAS_OBJECTS`).
   - Bypassing DeletionGuard or disabling immutability locks.
   - Disabling ransomware detection or security holds.

## Advanced Dependency Graph
The `DependencyGraphEngine` enforces logical reference validation before any deletion:
`Client -> Policy -> Workload -> Backup Job -> Run -> Recovery Point -> Manifest -> CAS Objects -> Replication -> Verification`
- If any Recovery Point references a `StorageObject`, it cannot be deleted by Garbage Collection.
- If a Recovery Point is the base of an active `BackupChain`, deletion is blocked.

## V8 Ransomware Security Integration
- If a Recovery Point is flagged under `SECURITY_HOLD`, deletion and pruning requests are rejected.
- Administrative triage and dual-approval are required to release security holds.
