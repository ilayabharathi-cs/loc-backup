# RetroVault Backup Engine — V10: Observability & Health Engine

## 1. Metrics Collection Architecture

The observability subsystem in `server/app/services/observability/` provides telemetry collection across 14 infrastructure components:

- **Agents**: Heartbeat age, OS version, software build, drift status.
- **Backup Jobs**: Execution duration, logical size, transfer size, dedup ratio, status.
- **Restore Jobs**: Recovery time objective (RTO), restored files/bytes, throughput (MB/s).
- **Replication**: Transferred bytes, sync duration, lag, pending jobs.
- **Repositories**: Total capacity, used bytes, free bytes, status.
- **Content Addressable Storage (CAS)**: Object count, stored bytes, deduplication savings.
- **Scheduler**: Queue depth, job wait times, task allocation.
- **Workers**: Worker utilization percentage, concurrency slots.
- **Cluster Nodes**: Node liveness, leader tenure, consensus lease expiration.
- **Database**: Ping latency (ms), connection pool utilization.
- **Security Engine**: Active security incidents, canary status, tampering attempts.

All metric samples are stored in `metric_samples`:
```python
class MetricSample(Base):
    metric_name: str
    value: float
    timestamp: datetime
    source: str
    labels_json: str  # Bounded, low-cardinality labels
    resolution: str   # RAW, HOURLY, DAILY
```

---

## 2. Rule-Based System Health Model

System health explicitly avoids arbitrary or opaque "AI scores". Component health evaluates strictly based on verifiable, deterministic operational rules.

### Component Health States
- `HEALTHY`: Component operates within all normal operating thresholds.
- `WARNING`: Sub-optimal operational parameters detected (e.g., agent heartbeat > 24h, storage utilization > 80%).
- `DEGRADED`: Degraded performance or partial component failure (e.g., repository offline, replication backlog).
- `CRITICAL`: Immediate administrator intervention required (e.g., database unreachable, critical security incidents active).
- `UNKNOWN`: Insufficient telemetry available to reach a conclusive state.

### Explicit Health Rules Table
| Component | Metric Evaluated | Rule / Threshold | State Assigned |
| :--- | :--- | :--- | :--- |
| **Database** | Ping Latency | Latency > 1000ms or unreachable | CRITICAL |
| **Cluster** | Node Liveness & Leader | Stale nodes > 0, or no active leader | DEGRADED |
| **Repositories** | Online Status & Utilization | Repositories OFFLINE or utilization > 90% | CRITICAL / DEGRADED |
| **Agents** | Heartbeat Latency | Heartbeat > 72h (Stale) | WARNING |
| **Backup Freshness**| Last Successful Run | No success within 48h | WARNING |
| **Restore Readiness**| Restore Failures | Restore failure count > 0 in 7 days | WARNING |
| **Security Engine** | Active Security Incidents | CRITICAL security incidents > 0 | CRITICAL |
| **Alerting** | Active Critical Alerts | Active alerts with CRITICAL severity | CRITICAL |

### Aggregate Health Determination
The overall system status adopts the **worst component state**:
$$\text{Overall Status} = \max(\text{Component Statuses})$$
with hierarchical precedence: $\text{CRITICAL} > \text{DEGRADED} > \text{WARNING} > \text{HEALTHY}$.

Every evaluation produces a comprehensive `overall_reason` string listing the exact components responsible for non-healthy states.

---

## 3. Telemetry Retention & Downsampling

### Downsampling Rollups
Raw metrics undergo automated aggregation via `TimeseriesService.downsample_metrics()`:
- Raw high-frequency samples $\rightarrow$ Hourly statistical buckets (average, min, max, sample count).
- Hourly buckets $\rightarrow$ Daily aggregates.

### Retention Pruning & Safety Invariant
The retention pruner enforces strict data hygiene while guaranteeing business continuity:
1. `raw_metric_retention_days` (default 30–90 days).
2. `aggregate_retention_days` (default 365 days).
3. `alert_retention_days` and `incident_retention_days`.

> [!IMPORTANT]
> **Safety Invariant**: Under NO circumstances does the telemetry retention pruner delete or alter Recovery Points, CAS objects, cryptographic hashes, security audit logs, or compliance evidence records.
