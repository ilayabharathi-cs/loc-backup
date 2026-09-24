# RetroVault Backup Engine — V10: Compliance Evidence Engine

## 1. Objective & Compliance Philosophy

The `ComplianceEvidenceService` in `server/app/services/observability/compliance_service.py` continuously discovers and indexes factual, auditable evidence across the enterprise backup platform.

> [!NOTE]
> RetroVault **never claims legal compliance automatically**. It generates verifiable evidence records with explicit states:
> - `EVIDENCE AVAILABLE`
> - `EVIDENCE MISSING`
> - `NOT APPLICABLE`
> - `UNKNOWN`

---

## 2. The 13 Compliance Domains

| Domain Code | Evaluated Criteria | Evidence Artifacts Checked |
| :--- | :--- | :--- |
| `BACKUP_EXECUTION` | Backup jobs dispatched & executed | `backup_runs` records |
| `BACKUP_SUCCESS` | Backup jobs completing without failure | `backup_runs` with status `completed` |
| `RETENTION` | Active retention policies assigned | `retention_policies` configuration |
| `IMMUTABILITY` | Repositories with WORM / Object-Lock | `storage_repositories.immutability_state` |
| `RESTORE_TESTS` | Disaster recovery / sandbox restore tests | Completed `restore_jobs` |
| `REPLICATION` | Offsite / multi-target replication sync | `replication_jobs` records |
| `INTEGRITY_SCANS` | CAS block SHA-256 bit-rot scans | `integrity_scans` with valid CAS objects |
| `ACCESS_CONTROL` | Active administrative user accounts | `users` directory and RBAC roles |
| `MFA` | Multi-Factor Authentication enforcement | TOTP configurations and MFA policies |
| `AUDIT_EVENTS` | Tamper-evident admin action logging | `audit_logs` activity trail |
| `POLICY_CHANGES` | Versioned schedule and policy changes | `backup_policies` change histories |
| `DELETION_APPROVALS` | Multi-person quorum for destructive operations| `deletion_guards` approval records |
| `SECURITY_INCIDENTS` | Ransomware & tampering event handling | `security_events` and incident resolutions |

---

## 3. Cryptographic Tamper-Evidence

Each `ComplianceEvidence` record is sealed with a canonical SHA-256 verification hash:

```python
payload_str = f"{domain}:{status}:{evidence_summary}:{json.dumps(details, sort_keys=True)}"
verification_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
```

When auditors inspect evidence in `/reports` or export compliance evidence via API, the system recomputes the SHA-256 hash to prove that stored evidence was not altered after generation.

---

## 4. Evidence Persistence Invariant

Compliance evidence records in `compliance_evidence` represent historical legal and auditing records. They have distinct retention rules and are **strictly protected from the operational telemetry downsampling pruner**.
