# RetroVault Backup Engine — V9: High Availability & Distributed Control Plane

## Executive Architecture Summary

RetroVault Backup Engine V9 elevates the platform from a single control-plane deployment into an **enterprise-grade, horizontally scalable, highly available distributed backup platform**.

```text
              Load Balancer / VIP (Layer 4/7)
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
      Node A         Node B        Node C
     Leader          Worker        Worker
  (Control Plane)  (Scheduler)  (Repo Worker)
        │             │             │
        └─────────────┼─────────────┘
                      │
              Distributed Queue (Atomic CAS)
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
     Backup        Restore       Replication
     Worker        Worker          Worker
                      │
                      ▼
           PostgreSQL High Availability
           (Patroni / Raft / PgBouncer)
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
        Local       Remote        S3
        Repo        Repo          Repo
```

---

## 1. Core Architectural Pillars

### 1.1 Leader Election Consensus & Split-Brain Prevention
- **Mechanism**: Lease-based consensus with TTL stored in `cluster_leases`.
- **Atomic Acquisition**: Single SQL statement Compare-And-Swap (`UPDATE ... WHERE lease_key = :k AND (owner_node_id = :id OR lease_expires_at < :now)`).
- **Split-Brain Guard**: Non-leader nodes attempting cluster reconciliation or exclusive coordination are strictly rejected.
- **Failover**: When a leader misses renewal or voluntarily resigns, competing healthy nodes safely claim the expired lease without double-master risk.

### 1.2 Distributed Resource Locks
- **Mechanism**: Fine-grained distributed resource locking (`distributed_locks`) with crash-safe expiration.
- **Mutual Exclusion**: Protects repository garbage collection, maintenance operations, and concurrent backup runs on identical client/repository pairs.
- **Crash Expiration**: If a node crashes while holding a lock, the TTL automatically expires the lock so subsequent operations are never permanently blocked.

### 1.3 Persistent Distributed Job Queue
- **Mechanism**: Priority-weighted persistent queue (`distributed_jobs`).
- **Atomic Compare-And-Swap (CAS)**:
  ```sql
  UPDATE distributed_jobs
  SET status = 'CLAIMED', owner_node_id = :node_id, started_at = :now, heartbeat_at = :now, attempt_count = attempt_count + 1
  WHERE id = :candidate_id AND status IN ('QUEUED', 'RETRYING')
  ```
- **Guarantees**: Zero race conditions between concurrent worker nodes. Returns row count; only the winning worker executes the job.
- **Fair Scheduling**: Concurrency bounds per client and repository ensure no single client starves the cluster worker pool.
- **Priority Aging**: Background reconciliation detects stagnant low-priority jobs and promotes priority weights over time to eliminate queue starvation.

### 1.4 Automatic Orphan Job Recovery
- **Failure Detection**: Worker nodes maintain continuous heartbeats. If a worker abruptly crashes or goes offline (`status = 'OFFLINE'`), or misses job heartbeats for $> 45$ seconds, its active jobs are tagged as `ORPHANED`.
- **Automatic Requeue**: If `attempt_count < max_attempts`, the orphan job is reset to `QUEUED` with cleared owner and backoff delay, allowing healthy surviving nodes to pick up and complete the workload without administrative intervention.
- **Terminal Exhaustion**: If maximum retries are exhausted, the job transitions to `FAILED` with detailed diagnostic error logs.

### 1.5 Zero-Downtime Rolling Maintenance
- **Lifecycle**: `ACTIVE` $\rightarrow$ `DRAINING` $\rightarrow$ `MAINTENANCE` $\rightarrow$ `ACTIVE`.
- **Draining Behavior**: When a node is set to `DRAINING`, it immediately stops accepting new job claims while permitting in-flight backup/restore/replication tasks to finish gracefully.
- **Resume**: Once upgrades or maintenance finish, toggling draining off immediately restores the node to `ACTIVE` to resume queue consumption.

---

## 2. Windows Agent Multi-Endpoint Failover

The Universal Windows Backup Agent (`agent/src/api_client.py`) supports multi-node cluster deployments:
- **Configuration**: `server_endpoints: ["http://node-a:8000", "http://node-b:8000", "http://node-c:8000"]`.
- **Automatic Failover**: If the active endpoint throws a connection failure or HTTP 500/502/503/504, the agent immediately fails over to the next configured cluster node using exponential backoff with jitter.
- **Zero Credential Loss**: Cryptographic hardware-backed device keys (`AgentCredentialManager`) and tokens are preserved across failovers.
- **Sticky Endpoint Retention**: Upon a successful request to a backup endpoint, the agent stays pinned to that healthy node until a subsequent failure occurs.

---

## 3. PostgreSQL HA vs SQLite Dialect Compatibility

| Feature | Local Deterministic Testing (SQLite) | Production Distributed Environment (PostgreSQL) |
|---|---|---|
| **Leader Consensus** | Atomic conditional `UPDATE` with row count | Atomic conditional `UPDATE` or `SELECT FOR UPDATE` |
| **Job Queue Claims** | Atomic `UPDATE ... WHERE id = :id AND status IN ('QUEUED', 'RETRYING')` | Atomic `UPDATE ... WHERE id = :id AND status IN ('QUEUED', 'RETRYING')` |
| **Distributed Locks** | Atomic `UPDATE ... WHERE expires_at < :now` | Atomic `UPDATE ... WHERE expires_at < :now` |
| **Orphan Recovery** | Heartbeat query + batch status reset | Heartbeat query + batch status reset |
| **High Availability Architecture** | Single-process embedded | Multi-node Patroni / Raft + PgBouncer Connection Pool |

> **Production Recommendation**: External Layer 4/7 Load Balancers (HAProxy, AWS ALB, F5) manage VIP and health checks against `/api/v1/cluster/status`. PostgreSQL clustering is managed by Patroni or managed cloud RDS/Aurora with multi-AZ failover.

---

## 4. Win95 Cluster & Scheduler Consoles

1. **/cluster (HA Cluster Console)**:
   - Live cluster health badge (`HEALTHY` / `DEGRADED`).
   - Active leader node identifier and lease TTL countdown.
   - Database layer metrics: Dialect (`PostgreSQL HA` / `SQLite Local`), latency, connection pool utilization.
   - Node grid with one-click **Drain Node**, **Resume Node**, **Nominate Leader**, and **Register Node** actions.
   - Live cluster event stream (`NODE_JOINED`, `LEADER_ELECTED`, `JOB_ORPHANED`, `FAILOVER_COMPLETED`).

2. **/scheduler (Distributed Scheduler & Worker Pools)**:
   - Worker pool categories (`BACKUP`, `RESTORE`, `REPLICATION`, `PRUNE`, `VERIFICATION`) with live progress bars.
   - Queue backpressure indicator (`NORMAL`, `MODERATE`, `HIGH`, `CRITICAL`).
   - Distributed jobs table with filtering by status and priority badges.
   - **Enqueue Job** and **Fleet Bulk Backup** dispatch triggers.
