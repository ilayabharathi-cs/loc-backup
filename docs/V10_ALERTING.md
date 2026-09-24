# RetroVault Backup Engine — V10: Alerting & Incident Management

## 1. Operational Alert Engine

The `AlertEvaluator` in `server/app/services/observability/alert_evaluator.py` provides real-time alerting with built-in storm suppression and deduplication.

### 17 Operational Alert Types
1. `BACKUP_MISSED`
2. `RPO_AT_RISK`
3. `RPO_MISSED`
4. `REPOSITORY_LOW_SPACE`
5. `REPOSITORY_OFFLINE`
6. `REPLICATION_LAG`
7. `AGENT_OFFLINE`
8. `AGENT_STALE`
9. `NODE_OFFLINE`
10. `SCHEDULER_BACKLOG`
11. `DATABASE_DEGRADED`
12. `RESTORE_FAILURE`
13. `INTEGRITY_FAILURE`
14. `SECURITY_EVENT`
15. `CONFIGURATION_DRIFT`
16. `CERTIFICATE_EXPIRY`
17. `CREDENTIAL_EXPIRY`

---

## 2. Fingerprint Deduplication & Cooldown

To avoid overwhelming monitoring consoles, alerts compute a deterministic fingerprint:
$$\text{fingerprint} = \text{SHA256}(\text{alert\_type} + \text{resource\_id} + \text{source})[:32]$$

### Deduplication Logic
1. When an alert arrives, the system queries for an existing active alert with matching `fingerprint`.
2. If found within the active cooldown window:
   - The alert is **not duplicated**.
   - `occurrence_count` increments by 1.
   - `last_seen` timestamp refreshes.
   - The existing alert record is returned.
3. If no active alert exists, a new record is created with `status = "ACTIVE"`.

---

## 3. Incident Correlation & Storm Suppression

When a root failure occurs (e.g., a primary storage SAN drops offline), dozens or hundreds of downstream client backups fail almost simultaneously. Instead of generating hundreds of disconnected notifications, the `IncidentService` correlates them into a unified `OperationalIncident`.

```text
       Primary Storage SAN Offline (Root Event)
                          │
       ┌──────────────────┼──────────────────┐
       ▼                  ▼                  ▼
 Client 1 Backup    Client 2 Backup    Client 3 Backup
     Failure            Failure            Failure
       │                  │                  │
       └──────────────────┼──────────────────┘
                          │
                          ▼
             Correlated OperationalIncident
             (INC-XXXX: Affected Resources: 3)
```

### Operational Incident Lifecycle
- `DETECTED`: Incident created and root event identified.
- `ACKNOWLEDGED`: On-call operator confirms receipt.
- `INVESTIGATING`: Root-cause investigation underway.
- `MITIGATING`: Corrective measures being applied.
- `MONITORING`: System observing recovery stability.
- `RESOLVED`: Root cause remediated; **all linked child alerts are automatically resolved**.
- `CLOSED`: Post-incident review completed.
