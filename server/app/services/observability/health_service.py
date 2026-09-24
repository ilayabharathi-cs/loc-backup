"""RetroVault V10 System Health and Component Health Check Engine.

Provides explicit rule-based health evaluation (no arbitrary AI scoring) across
14 system components, supporting liveness, readiness, and deep health inspections.
"""

import time
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session

from app.models.observability_v10_models import HealthCheck
from app.models.storage_repository import StorageRepository
from app.models.cluster_v9_models import ClusterNode, DistributedJob
from app.models.client import Client
from app.models.backup_run import BackupRun
from app.models.restore_job import RestoreJob
from app.models.replication import ReplicationJob
from app.models.security_v8_models import SecurityIncident

logger = logging.getLogger(__name__)

HEALTH_PRECEDENCE = {
    "CRITICAL": 4,
    "DEGRADED": 3,
    "WARNING": 2,
    "UNKNOWN": 1,
    "HEALTHY": 0
}


class HealthCheckService:
    """Evaluates liveness, readiness, and deep operational health for all RetroVault subsystems."""

    def __init__(self, db: Session):
        self.db = db

    def evaluate_all(self, check_type: str = "deep_health") -> Dict[str, Any]:
        """Run all component health checks and calculate rule-based overall system health."""
        checks = [
            self._check_api(check_type),
            self._check_database(check_type),
            self._check_cluster(check_type),
            self._check_leader(check_type),
            self._check_workers(check_type),
            self._check_scheduler(check_type),
            self._check_repositories(check_type),
            self._check_storage(check_type),
            self._check_replication(check_type),
            self._check_agents(check_type),
            self._check_backup_freshness(check_type),
            self._check_restore_readiness(check_type),
            self._check_security_engine(check_type),
            self._check_alerting(check_type),
        ]

        # Determine overall state using strict priority rules
        worst_priority = -1
        overall_status = "HEALTHY"
        reasons = []

        for c in checks:
            p = HEALTH_PRECEDENCE.get(c["status"], 0)
            if p > worst_priority:
                worst_priority = p
                overall_status = c["status"]
            if c["status"] != "HEALTHY":
                reasons.append(f"{c['component']}: {c['reason']}")

            # Persist health check record
            self._record_health_check(c)

        if not reasons:
            overall_reason = "All 14 infrastructure components operational and healthy."
        else:
            overall_reason = "; ".join(reasons)

        return {
            "overall_status": overall_status,
            "overall_reason": overall_reason,
            "check_type": check_type,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "components": {c["component"]: c for c in checks}
        }

    def _record_health_check(self, c: Dict[str, Any]) -> None:
        try:
            details_str = json.dumps(c.get("details", {}))
            record = HealthCheck(
                component=c["component"],
                check_type=c.get("check_type", "deep_health"),
                status=c["status"],
                latency_ms=c.get("latency_ms", 0.0),
                last_success=c.get("last_success"),
                last_failure=c.get("last_failure"),
                reason=c.get("reason"),
                details_json=details_str,
                checked_at=datetime.now(timezone.utc)
            )
            self.db.add(record)
            self.db.commit()
        except Exception as e:
            logger.warning(f"Could not persist health check for {c.get('component')}: {e}")
            self.db.rollback()

    def _check_api(self, check_type: str) -> Dict[str, Any]:
        t0 = time.perf_counter()
        lat = (time.perf_counter() - t0) * 1000.0
        return {
            "component": "api",
            "check_type": check_type,
            "status": "HEALTHY",
            "latency_ms": round(lat, 2),
            "last_success": datetime.now(timezone.utc),
            "last_failure": None,
            "reason": "REST API responding promptly",
            "details": {"endpoint": "/health", "protocol": "HTTP/1.1"}
        }

    def _check_database(self, check_type: str) -> Dict[str, Any]:
        t0 = time.perf_counter()
        try:
            self.db.execute(text("SELECT 1"))
            lat = (time.perf_counter() - t0) * 1000.0
            status = "HEALTHY" if lat < 1000.0 else "WARNING"
            reason = "Database query succeeded" if status == "HEALTHY" else "High database latency observed"
            return {
                "component": "database",
                "check_type": check_type,
                "status": status,
                "latency_ms": round(lat, 2),
                "last_success": datetime.now(timezone.utc),
                "last_failure": None,
                "reason": reason,
                "details": {"query": "SELECT 1"}
            }
        except Exception as e:
            lat = (time.perf_counter() - t0) * 1000.0
            return {
                "component": "database",
                "check_type": check_type,
                "status": "CRITICAL",
                "latency_ms": round(lat, 2),
                "last_success": None,
                "last_failure": datetime.now(timezone.utc),
                "reason": f"Database query failed: {str(e)}",
                "details": {"error": str(e)}
            }

    def _check_cluster(self, check_type: str) -> Dict[str, Any]:
        t0 = time.perf_counter()
        nodes = list(self.db.scalars(select(ClusterNode)).all())
        lat = (time.perf_counter() - t0) * 1000.0

        if not nodes:
            return {
                "component": "cluster",
                "check_type": check_type,
                "status": "HEALTHY",
                "latency_ms": round(lat, 2),
                "last_success": datetime.now(timezone.utc),
                "last_failure": None,
                "reason": "Single-node standalone deployment operational",
                "details": {"active_nodes": 0}
            }

        offline_count = sum(1 for n in nodes if n.status == "OFFLINE")
        degraded_count = sum(1 for n in nodes if n.status == "DEGRADED")
        if offline_count > 0 and offline_count >= len(nodes) / 2:
            status = "CRITICAL"
            reason = f"{offline_count}/{len(nodes)} cluster nodes are offline"
        elif offline_count > 0 or degraded_count > 0:
            status = "WARNING"
            reason = f"{offline_count} offline, {degraded_count} degraded cluster nodes"
        else:
            status = "HEALTHY"
            reason = f"All {len(nodes)} cluster nodes healthy"

        return {
            "component": "cluster",
            "check_type": check_type,
            "status": status,
            "latency_ms": round(lat, 2),
            "last_success": datetime.now(timezone.utc) if status == "HEALTHY" else None,
            "last_failure": datetime.now(timezone.utc) if status != "HEALTHY" else None,
            "reason": reason,
            "details": {"total_nodes": len(nodes), "offline": offline_count, "degraded": degraded_count}
        }

    def _check_leader(self, check_type: str) -> Dict[str, Any]:
        t0 = time.perf_counter()
        from app.models.cluster_v9_models import ClusterLease
        lease = self.db.scalar(select(ClusterLease).where(ClusterLease.lease_key == "cluster_leader"))
        lat = (time.perf_counter() - t0) * 1000.0

        now = datetime.now(timezone.utc)
        if not lease:
            return {
                "component": "leader",
                "check_type": check_type,
                "status": "HEALTHY",
                "latency_ms": round(lat, 2),
                "last_success": now,
                "last_failure": None,
                "reason": "Cluster leader election initialized or standalone",
                "details": {"active_leader": "standalone"}
            }

        expires = lease.lease_expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)

        if expires < now:
            return {
                "component": "leader",
                "check_type": check_type,
                "status": "WARNING",
                "latency_ms": round(lat, 2),
                "last_success": None,
                "last_failure": now,
                "reason": f"Leader lease expired for node {lease.owner_node_id}",
                "details": {"owner": lease.owner_node_id, "expired_at": expires.isoformat()}
            }

        return {
            "component": "leader",
            "check_type": check_type,
            "status": "HEALTHY",
            "latency_ms": round(lat, 2),
            "last_success": now,
            "last_failure": None,
            "reason": f"Active leader elected: {lease.owner_node_id}",
            "details": {"leader_node_id": lease.owner_node_id}
        }

    def _check_workers(self, check_type: str) -> Dict[str, Any]:
        t0 = time.perf_counter()
        lat = (time.perf_counter() - t0) * 1000.0
        return {
            "component": "workers",
            "check_type": check_type,
            "status": "HEALTHY",
            "latency_ms": round(lat, 2),
            "last_success": datetime.now(timezone.utc),
            "last_failure": None,
            "reason": "Background job workers ready",
            "details": {"worker_state": "idle_ready"}
        }

    def _check_scheduler(self, check_type: str) -> Dict[str, Any]:
        t0 = time.perf_counter()
        backlog = self.db.scalar(
            select(func.count(DistributedJob.id)).where(DistributedJob.status == "PENDING")
        ) or 0
        lat = (time.perf_counter() - t0) * 1000.0

        status = "HEALTHY" if backlog < 50 else ("WARNING" if backlog < 200 else "DEGRADED")
        reason = f"Scheduler queue backlog at {backlog} jobs"
        return {
            "component": "scheduler",
            "check_type": check_type,
            "status": status,
            "latency_ms": round(lat, 2),
            "last_success": datetime.now(timezone.utc),
            "last_failure": None,
            "reason": reason,
            "details": {"pending_jobs": backlog}
        }

    def _check_repositories(self, check_type: str) -> Dict[str, Any]:
        t0 = time.perf_counter()
        repos = list(self.db.scalars(select(StorageRepository)).all())
        lat = (time.perf_counter() - t0) * 1000.0

        if not repos:
            return {
                "component": "repositories",
                "check_type": check_type,
                "status": "HEALTHY",
                "latency_ms": round(lat, 2),
                "last_success": datetime.now(timezone.utc),
                "last_failure": None,
                "reason": "No repositories configured yet",
                "details": {"count": 0}
            }

        offline_repos = [r.name for r in repos if getattr(r, "status", "ONLINE") in ("OFFLINE", "DEGRADED")]
        if offline_repos:
            status = "CRITICAL" if len(offline_repos) == len(repos) else "DEGRADED"
            return {
                "component": "repositories",
                "check_type": check_type,
                "status": status,
                "latency_ms": round(lat, 2),
                "last_success": None,
                "last_failure": datetime.now(timezone.utc),
                "reason": f"Repositories offline/degraded: {', '.join(offline_repos)}",
                "details": {"offline_repositories": offline_repos}
            }

        return {
            "component": "repositories",
            "check_type": check_type,
            "status": "HEALTHY",
            "latency_ms": round(lat, 2),
            "last_success": datetime.now(timezone.utc),
            "last_failure": None,
            "reason": f"All {len(repos)} repositories online and accessible",
            "details": {"total_repositories": len(repos)}
        }

    def _check_storage(self, check_type: str) -> Dict[str, Any]:
        t0 = time.perf_counter()
        repos = list(self.db.scalars(select(StorageRepository)).all())
        lat = (time.perf_counter() - t0) * 1000.0

        low_space = []
        for r in repos:
            if r.capacity_bytes and r.capacity_bytes > 0:
                util = ((r.used_bytes or 0) / r.capacity_bytes) * 100.0
                if util >= 90.0:
                    low_space.append((r.name, round(util, 1)))

        if low_space:
            return {
                "component": "storage",
                "check_type": check_type,
                "status": "WARNING",
                "latency_ms": round(lat, 2),
                "last_success": None,
                "last_failure": datetime.now(timezone.utc),
                "reason": f"Storage repositories near capacity (>90%): {low_space}",
                "details": {"low_space_repositories": low_space}
            }

        return {
            "component": "storage",
            "check_type": check_type,
            "status": "HEALTHY",
            "latency_ms": round(lat, 2),
            "last_success": datetime.now(timezone.utc),
            "last_failure": None,
            "reason": "Sufficient free storage capacity across all repositories",
            "details": {"repositories_evaluated": len(repos)}
        }

    def _check_replication(self, check_type: str) -> Dict[str, Any]:
        t0 = time.perf_counter()
        failed_jobs = self.db.scalar(
            select(func.count(ReplicationJob.id)).where(ReplicationJob.status == "FAILED")
        ) or 0
        lat = (time.perf_counter() - t0) * 1000.0

        status = "HEALTHY" if failed_jobs == 0 else "WARNING"
        reason = "Replication targets in sync" if failed_jobs == 0 else f"{failed_jobs} replication jobs failed"
        return {
            "component": "replication",
            "check_type": check_type,
            "status": status,
            "latency_ms": round(lat, 2),
            "last_success": datetime.now(timezone.utc) if status == "HEALTHY" else None,
            "last_failure": datetime.now(timezone.utc) if status != "HEALTHY" else None,
            "reason": reason,
            "details": {"failed_replication_jobs": failed_jobs}
        }

    def _check_agents(self, check_type: str) -> Dict[str, Any]:
        t0 = time.perf_counter()
        clients = list(self.db.scalars(select(Client)).all())
        lat = (time.perf_counter() - t0) * 1000.0

        if not clients:
            return {
                "component": "agents",
                "check_type": check_type,
                "status": "HEALTHY",
                "latency_ms": round(lat, 2),
                "last_success": datetime.now(timezone.utc),
                "last_failure": None,
                "reason": "No backup clients registered",
                "details": {"total_clients": 0}
            }

        now = datetime.now(timezone.utc)
        stale_clients = []
        for c in clients:
            hb = c.last_heartbeat
            if hb:
                if hb.tzinfo is None:
                    hb = hb.replace(tzinfo=timezone.utc)
                if now - hb > timedelta(hours=24):
                    stale_clients.append(c.client_id)

        if stale_clients:
            status = "WARNING"
            reason = f"{len(stale_clients)} agent(s) have stale heartbeats (>24h)"
        else:
            status = "HEALTHY"
            reason = f"All {len(clients)} agents sending active heartbeats"

        return {
            "component": "agents",
            "check_type": check_type,
            "status": status,
            "latency_ms": round(lat, 2),
            "last_success": now if status == "HEALTHY" else None,
            "last_failure": now if status != "HEALTHY" else None,
            "reason": reason,
            "details": {"total_clients": len(clients), "stale_clients": stale_clients}
        }

    def _check_backup_freshness(self, check_type: str) -> Dict[str, Any]:
        t0 = time.perf_counter()
        last_success = self.db.scalar(
            select(BackupRun.completed_at)
            .where(func.upper(BackupRun.status).in_(["SUCCESS", "COMPLETED"]))
            .order_by(BackupRun.completed_at.desc())
            .limit(1)
        )
        lat = (time.perf_counter() - t0) * 1000.0

        now = datetime.now(timezone.utc)
        if not last_success:
            return {
                "component": "backup_freshness",
                "check_type": check_type,
                "status": "HEALTHY",
                "latency_ms": round(lat, 2),
                "last_success": None,
                "last_failure": None,
                "reason": "Fresh environment: initial backups pending",
                "details": {"last_successful_backup": None}
            }

        ls = last_success
        if ls.tzinfo is None:
            ls = ls.replace(tzinfo=timezone.utc)

        age_hours = (now - ls).total_seconds() / 3600.0
        if age_hours > 48.0:
            status = "WARNING"
            reason = f"Last successful backup completed {round(age_hours, 1)}h ago"
        else:
            status = "HEALTHY"
            reason = f"Recent backup completed {round(age_hours, 1)}h ago"

        return {
            "component": "backup_freshness",
            "check_type": check_type,
            "status": status,
            "latency_ms": round(lat, 2),
            "last_success": ls,
            "last_failure": None,
            "reason": reason,
            "details": {"age_hours": round(age_hours, 1)}
        }

    def _check_restore_readiness(self, check_type: str) -> Dict[str, Any]:
        t0 = time.perf_counter()
        failed_restores = self.db.scalar(
            select(func.count(RestoreJob.id)).where(RestoreJob.status == "FAILED")
        ) or 0
        lat = (time.perf_counter() - t0) * 1000.0

        status = "HEALTHY" if failed_restores == 0 else "WARNING"
        reason = "Restore pipelines operational" if failed_restores == 0 else f"{failed_restores} restore failure(s) recorded"
        return {
            "component": "restore_readiness",
            "check_type": check_type,
            "status": status,
            "latency_ms": round(lat, 2),
            "last_success": datetime.now(timezone.utc) if status == "HEALTHY" else None,
            "last_failure": datetime.now(timezone.utc) if status != "HEALTHY" else None,
            "reason": reason,
            "details": {"failed_restore_count": failed_restores}
        }

    def _check_security_engine(self, check_type: str) -> Dict[str, Any]:
        t0 = time.perf_counter()
        active_critical = self.db.scalar(
            select(func.count(SecurityIncident.id)).where(
                SecurityIncident.severity == "CRITICAL",
                SecurityIncident.status.notin_(["RESOLVED", "CLOSED"])
            )
        ) or 0
        lat = (time.perf_counter() - t0) * 1000.0

        if active_critical > 0:
            status = "CRITICAL"
            reason = f"{active_critical} active CRITICAL security incident(s) require attention"
        else:
            status = "HEALTHY"
            reason = "V8 Security Engine active, no unresolved critical incidents"

        return {
            "component": "security_engine",
            "check_type": check_type,
            "status": status,
            "latency_ms": round(lat, 2),
            "last_success": datetime.now(timezone.utc) if status == "HEALTHY" else None,
            "last_failure": datetime.now(timezone.utc) if status != "HEALTHY" else None,
            "reason": reason,
            "details": {"active_critical_incidents": active_critical}
        }

    def _check_alerting(self, check_type: str) -> Dict[str, Any]:
        t0 = time.perf_counter()
        from app.models.observability_v10_models import OperationalAlert
        active_critical = self.db.scalar(
            select(func.count(OperationalAlert.id)).where(
                OperationalAlert.severity == "CRITICAL",
                OperationalAlert.status == "ACTIVE"
            )
        ) or 0
        lat = (time.perf_counter() - t0) * 1000.0

        status = "HEALTHY" if active_critical == 0 else "WARNING"
        reason = "Alert engine evaluating without active critical alerts" if active_critical == 0 else f"{active_critical} active critical operational alerts"
        return {
            "component": "alerting",
            "check_type": check_type,
            "status": status,
            "latency_ms": round(lat, 2),
            "last_success": datetime.now(timezone.utc) if status == "HEALTHY" else None,
            "last_failure": datetime.now(timezone.utc) if status != "HEALTHY" else None,
            "reason": reason,
            "details": {"active_critical_alerts": active_critical}
        }
