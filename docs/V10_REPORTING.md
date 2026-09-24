# RetroVault Backup Engine — V10: Enterprise Reporting Engine

## 1. Overview

The `ReportGeneratorService` in `server/app/services/observability/report_generator.py` provides factual, reproducible enterprise report compilation and export capabilities.

---

## 2. Supported Report Templates

1. **Backup Operations Report**: Summary of successful, failed, and in-progress backup runs, data throughput, and logical vs. physical storage.
2. **Recovery Readiness Report**: Disaster recovery restore drill history, measured RTO performance, and sandbox verification logs.
3. **Security Controls Report**: Immutability configurations, MFA status, tampering attempts, and active security incidents.
4. **Access Control Report**: Administrative users, RBAC roles, active sessions, and privilege allocations.
5. **Retention Policy Report**: Retention policies, security hold dates, and legal hold locks.
6. **Immutability Report**: WORM repositories, retention-locked tiers, and object-lock enforcement.
7. **Replication Report**: Offsite data transfer volumes, sync durations, replication lag, and failed transfers.
8. **Audit Activity Report**: Filtered administrative actions, user logins, policy modifications, and deletion requests.
9. **Fleet Health Report**: Windows agent heartbeat freshness, OS distributions, version parity, and configuration drift.
10. **Capacity Forecast Report**: Storage utilization snapshots, 7/30/90-day mathematical forecasts, and exhaustion dates.
11. **Compliance Evidence Report**: 13-domain compliance evidence status and SHA-256 verification hashes.

---

## 3. Multi-Format Export Architecture

Every compiled report can be exported into three standard enterprise formats:

- **JSON Artifact**: Raw structured machine-readable payload containing system version, scope, period, generated timestamp, summary metrics, and detail rows.
- **CSV Spreadsheet**: Flat tabular format with header rows, suitable for ingestion into BI systems (Tableau, PowerBI, Excel).
- **PDF Document**: Executive document rendered via ReportLab with corporate headers, summary metric blocks, and tabular evidence rows.

### Cryptographic Verification Checksum
Upon export, the artifact file is hashed with SHA-256 and stored in `report_executions`:
```python
checksum_sha256 = hashlib.sha256(file_bytes).hexdigest()
```
This enables auditors to prove the integrity and provenance of any exported report artifact.
