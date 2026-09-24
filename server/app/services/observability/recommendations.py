"""RetroVault V10 Operational Recommendation Engine.

Generates strictly explainable, evidence-backed advisory recommendations.
Never performs autonomous destructive remediation.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.storage_repository import StorageRepository
from app.models.client import Client
from app.models.replication import ReplicationJob
from app.models.cluster_v9_models import ClusterNode
from app.services.observability.rpo_monitor import BackupObjectiveMonitor

logger = logging.getLogger(__name__)


class RecommendationEngine:
    """Evaluates factual operational telemetry and derives actionable, auditable recommendations."""

    def __init__(self, db: Session):
        self.db = db

    def evaluate_recommendations(self) -> List[Dict[str, Any]]:
        """Run all factual rules to generate advisory operational recommendations."""
        recommendations = []
        now = datetime.now(timezone.utc)

        # 1. Storage repository utilization rule
        repos = list(self.db.scalars(select(StorageRepository)).all())
        for r in repos:
            if r.capacity_bytes and r.capacity_bytes > 0:
                util = ((r.used_bytes or 0) / r.capacity_bytes) * 100.0
                if util >= 85.0:
                    severity = "CRITICAL" if util >= 95.0 else "WARNING"
                    recommendations.append({
                        "id": f"REC-STORAGE-{r.id}",
                        "severity": severity,
                        "affected_resource": f"Repository:{r.name} (id={r.id})",
                        "reason": f"Repository {r.name} has reached {round(util, 1)}% capacity utilization.",
                        "evidence": {
                            "used_bytes": r.used_bytes,
                            "capacity_bytes": r.capacity_bytes,
                            "utilization_pct": round(util, 1)
                        },
                        "recommended_action": f"Expand storage volume for repository '{r.name}' or adjust retention policies to reclaim expired recovery points.",
                        "generated_at": now.isoformat(),
                        "is_automated_execution_allowed": False
                    })

        # 2. Replication failures rule
        rep_cutoff = now - timedelta(hours=24)
        rep_failures = self.db.scalar(
            select(func.count(ReplicationJob.id)).where(
                ReplicationJob.status == "FAILED",
                ReplicationJob.created_at >= rep_cutoff
            )
        ) or 0
        if rep_failures > 0:
            recommendations.append({
                "id": "REC-REPLICATION-FAILURES",
                "severity": "WARNING",
                "affected_resource": "ReplicationSubsystem",
                "reason": f"Replication engine experienced {rep_failures} failed job(s) in the last 24 hours.",
                "evidence": {
                    "failures_in_24h": rep_failures,
                    "evaluation_window": "24h"
                },
                "recommended_action": "Verify secondary replication target network connectivity and authentication credentials.",
                "generated_at": now.isoformat(),
                "is_automated_execution_allowed": False
            })

        # 3. Client RPO missed rule
        rpo_monitor = BackupObjectiveMonitor(self.db)
        clients = list(self.db.scalars(select(Client)).all())
        for c in clients:
            eval_res = rpo_monitor.evaluate_client_rpo(c.client_id)
            if eval_res.get("status") == "MISSED":
                obs_rpo = eval_res.get("observed_rpo_hours")
                tgt_rpo = eval_res.get("rpo_target_hours")
                recommendations.append({
                    "id": f"REC-RPO-MISSED-{c.id}",
                    "severity": "HIGH",
                    "affected_resource": f"Client:{c.client_id} ({c.hostname})",
                    "reason": f"Client {c.hostname} has missed its configured backup objective ({obs_rpo}h observed vs {tgt_rpo}h target).",
                    "evidence": {
                        "client_id": c.client_id,
                        "observed_rpo_hours": obs_rpo,
                        "target_rpo_hours": tgt_rpo,
                        "last_success": eval_res.get("last_success")
                    },
                    "recommended_action": f"Investigate agent service status on host '{c.hostname}' or trigger an on-demand incremental backup.",
                    "generated_at": now.isoformat(),
                    "is_automated_execution_allowed": False
                })

        # 4. Agent version drift / mismatch rule
        versions = {}
        for c in clients:
            ver = c.agent_version or "unknown"
            versions[ver] = versions.get(ver, 0) + 1
        if len(versions) > 1:
            dominant_ver = max(versions, key=versions.get)
            mismatched_clients = [c.client_id for c in clients if c.agent_version != dominant_ver]
            recommendations.append({
                "id": "REC-AGENT-VERSION-DRIFT",
                "severity": "INFO",
                "affected_resource": "Fleet:WindowsAgents",
                "reason": f"Agent version mismatch detected across {len(mismatched_clients)} client(s).",
                "evidence": {
                    "version_distribution": versions,
                    "target_standard_version": dominant_ver,
                    "mismatched_client_ids": mismatched_clients
                },
                "recommended_action": f"Schedule remote agent MSI upgrade rollout to align fleet with version {dominant_ver}.",
                "generated_at": now.isoformat(),
                "is_automated_execution_allowed": False
            })

        # 5. Cluster nodes degraded/offline rule
        cluster_nodes = list(self.db.scalars(select(ClusterNode)).all())
        offline_nodes = [n.node_id for n in cluster_nodes if n.status == "OFFLINE"]
        if offline_nodes:
            recommendations.append({
                "id": "REC-CLUSTER-OFFLINE-NODES",
                "severity": "HIGH",
                "affected_resource": "Cluster:Nodes",
                "reason": f"Cluster node(s) offline: {offline_nodes}",
                "evidence": {
                    "offline_nodes": offline_nodes,
                    "total_nodes": len(cluster_nodes)
                },
                "recommended_action": "Check process supervisor / service status on offline cluster member nodes.",
                "generated_at": now.isoformat(),
                "is_automated_execution_allowed": False
            })

        return recommendations
