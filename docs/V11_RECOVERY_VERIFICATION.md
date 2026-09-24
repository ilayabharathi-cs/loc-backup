# RetroVault V11 Synthetic Recovery & Automated Verification

## Objective & Invariants
The Recovery Verification Engine regularly proves that backups are recoverable without touching production data:
1. **Isolated Sandbox Target**: Every verification runs inside an isolated sandbox path (`tempfile.gettempdir()/retrovault_sandbox/<verification_id>`).
2. **Zero Production Risk**: Production files, volumes, and databases are never overwritten during verification.
3. **Automatic Sandbox Cleanup**: Sandbox directories are automatically pruned upon test completion to prevent disk leaks.

## Verification Types

| Type | Target Verified | Validation Method |
|---|---|---|
| `MANIFEST` | Recovery Point metadata | Validates manifest syntax, file count, and schema consistency |
| `CHECKSUM` | CAS storage objects | Recomputes SHA-256 digests and checks against repository records |
| `FULL_RESTORE` | File payload | Performs full file extraction into sandbox directory |
| `APPLICATION_ARTIFACT` | Database / Dump file | Validates archive headers and formats |
| `DATABASE_VALIDATION` | Database pages / LSNs | Validates database headers, page consistency, and LSN continuity |
| `RECONSTRUCTION` | Point-in-time state | Rebuilds point-in-time state from baseline + log chain in sandbox |

## Verification Execution Pipeline
1. `MANIFEST_VERIFICATION`: Verifies Recovery Point existence and validity.
2. `CAS_CHECKSUM_VERIFICATION`: Verifies SHA-256 hashes of all referenced objects.
3. `SANDBOX_EXTRACTION`: Extracts artifacts into the isolated sandbox directory.
4. `APP_PAYLOAD_VALIDATION`: Executes header or format validation.
5. `CLEANUP`: Removes temporary sandbox directory.

## Factual Recovery Readiness Intelligence
Recovery Readiness calculates readiness across 11 measurable signals without arbitrary scores:
1. **Latest Successful Backup**: Elapsed time since last backup against configured RPO.
2. **Latest Verified Recovery Point**: Verified synthetic restore status.
3. **Object Integrity**: CAS storage corruption count.
4. **Replication Status**: Offsite replication sync failures.
5. **Retention Protection**: Active retention policy status.
6. **Verification Failure History**: Recent failed verification runs.
7. **RPO Compliance**: Factual compliance percentage.
8. **Observed RTO**: Factual restore duration observations.
9. **Unresolved Security Holds**: Active `SECURITY_HOLD` locks.
10. **Unresolved Incidents**: Open operational incidents.
11. **Repository Health**: Offline or degraded storage repositories.

Verdict States: `READY`, `DEGRADED`, `NOT_READY`, `UNKNOWN`.
