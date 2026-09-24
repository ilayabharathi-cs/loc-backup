# RetroVault V11 Operational Guide

## Day-to-Day Operations

### 1. Workload Discovery
To discover workloads on a client:
```bash
POST /api/v1/workloads/{client_id}/discover
Content-Type: application/json

{
  "provider_type": "MSSQL"
}
```

### 2. Triggering Application-Aware Backup
To trigger an application-aware backup:
```bash
POST /api/v1/workloads/{workload_id}/protect
Content-Type: application/json

{
  "backup_type": "FULL"
}
```

### 3. Application Restore Preview & Execution
Before restoring, always generate a restore preview to check overwrite conflicts:
```bash
POST /api/v1/workloads/{workload_id}/restore-preview
Content-Type: application/json

{
  "recovery_point_id": "1",
  "target_destination": "C:\\Restored_DB",
  "recovery_mode": "APPLICATION_RESTORE"
}
```

Execute validated restore:
```bash
POST /api/v1/workloads/{workload_id}/restore
Content-Type: application/json

{
  "recovery_point_id": "1",
  "target_destination": "C:\\Restored_DB",
  "recovery_mode": "APPLICATION_RESTORE"
}
```

### 4. Synthetic Restore Verification
To queue a verification test:
```bash
POST /api/v1/recovery-verification
Content-Type: application/json

{
  "recovery_point_id": "1",
  "workload_id": "mssql-1-coreerp",
  "verification_type": "CHECKSUM"
}
```

### 5. Policy Lifecycle & Rollback
Create version:
```bash
POST /api/v1/policy-orchestration
{
  "policy_id": "pol-production",
  "definition": {"schedule": "0 2 * * *", "retention_days": 30}
}
```

Approve and activate:
```bash
POST /api/v1/policy-orchestration/{id}/approve
POST /api/v1/policy-orchestration/{id}/activate
```
