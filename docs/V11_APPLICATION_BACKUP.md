# RetroVault V11 Application-Aware Backup & Consistency Engine

## Workflow Overview
Application-aware backup protects stateful enterprise workloads by coordinating quiescing, snapshotting, and evidence-based consistency verification before persisting artifacts into Content-Addressed Storage (CAS).

## Protection Lifecycle States
During execution, a workload progresses through explicit audited states:
1. `DISCOVERED`: Discovered on client and registered in inventory.
2. `PREPARING`: Pre-snapshot hook checks connectivity and prerequisites.
3. `QUIESCING`: Application quiescing freeze initiated (VSS writer, MVCC, or custom hook).
4. `BACKING_UP`: Snapshot artifact generation and physical transfer.
5. `VERIFYING`: Post-thaw consistency verification and checksum validation.
6. `COMPLETING`: CAS StorageObject registration, BackupChain updates, and RecoveryPoint creation.
7. `COMPLETED`: Finished successfully with evidence recorded.
8. `FAILED`: Failed with actionable diagnostics recorded in audit logs.

## Application Consistency States
RetroVault rejects deceptive consistency claims. A Recovery Point is assigned one of the following evidence-based states:
- `APPLICATION_CONSISTENT`: Quiesce succeeded, transaction log or checkpoint LSN confirmed, and artifacts verified without torn pages or truncation.
- `FILE_SYSTEM_CONSISTENT`: VSS snapshot captured filesystem metadata cleanly without application-level writer coordination.
- `CRASH_CONSISTENT`: Application was snapshotted without prior quiescing; state is equivalent to an abrupt power cut.
- `PARTIAL`: Some components of a composite application were quiesced while others failed.
- `UNKNOWN`: Insufficient evidence or unverified third-party snapshot.
- `FAILED`: Pre-hook or backup snapshot aborted with error.

## Backup Chain Architecture
Each application-aware backup participates in a `BackupChain`:
- Tracks `base_recovery_point_id` (the full baseline) and sequential incremental/log points.
- Continuous validation detects broken chains caused by missing baseline points, corrupted CAS objects, or expired dependencies.
- Exposes chain health: `VALID`, `DEGRADED`, `BROKEN`, `UNKNOWN`.
