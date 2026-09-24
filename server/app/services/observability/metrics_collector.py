"""RetroVault V10 Metrics Collector Subsystem.

Collects, standardizes, batches, and ingests metrics across agents, backup jobs,
restore jobs, replication, repositories, CAS, scheduler, workers, cluster nodes,
database, security engine, storage, and network transfer.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session

from app.models.observability_v10_models import MetricSample

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Centralized metrics ingestion and on-demand sampling service."""

    def __init__(self, db: Session):
        self.db = db

    def record_metric(
        self,
        metric_name: str,
        value: float,
        source: str,
        labels: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
        granularity: str = "RAW"
    ) -> MetricSample:
        """Record an individual metric sample."""
        ts = timestamp or datetime.now(timezone.utc)
        labels_json = json.dumps(labels, sort_keys=True) if labels else None

        sample = MetricSample(
            metric_name=metric_name,
            value=float(value),
            timestamp=ts,
            source=source,
            labels_json=labels_json,
            granularity=granularity,
            sample_count=1,
            min_value=float(value),
            max_value=float(value),
            sum_value=float(value)
        )
        self.db.add(sample)
        self.db.commit()
        self.db.refresh(sample)
        return sample

    def record_metrics_batch(self, samples_data: Sequence[Dict[str, Any]]) -> int:
        """Batch record a collection of metric samples for high-throughput efficiency."""
        if not samples_data:
            return 0

        now = datetime.now(timezone.utc)
        objects = []
        for item in samples_data:
            val = float(item["value"])
            labels = item.get("labels")
            labels_json = json.dumps(labels, sort_keys=True) if labels else None
            ts = item.get("timestamp") or now
            obj = MetricSample(
                metric_name=item["metric_name"],
                value=val,
                timestamp=ts,
                source=item.get("source", "system"),
                labels_json=labels_json,
                granularity=item.get("granularity", "RAW"),
                sample_count=item.get("sample_count", 1),
                min_value=float(item.get("min_value", val)),
                max_value=float(item.get("max_value", val)),
                sum_value=float(item.get("sum_value", val))
            )
            objects.append(obj)

        self.db.bulk_save_objects(objects)
        self.db.commit()
        return len(objects)

    def query_metrics(
        self,
        metric_name: Optional[str] = None,
        source: Optional[str] = None,
        granularity: str = "RAW",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 500,
        offset: int = 0
    ) -> List[MetricSample]:
        """Query stored metric samples with pagination and filters."""
        stmt = select(MetricSample)
        if metric_name:
            stmt = stmt.where(MetricSample.metric_name == metric_name)
        if source:
            stmt = stmt.where(MetricSample.source == source)
        if granularity:
            stmt = stmt.where(MetricSample.granularity == granularity)
        if start_time:
            stmt = stmt.where(MetricSample.timestamp >= start_time)
        if end_time:
            stmt = stmt.where(MetricSample.timestamp <= end_time)

        stmt = stmt.order_by(desc(MetricSample.timestamp)).offset(offset).limit(limit)
        return list(self.db.scalars(stmt).all())

    def collect_live_system_metrics(self) -> Dict[str, Any]:
        """Collect and persist live point-in-time metrics across all core system domains."""
        now = datetime.now(timezone.utc)
        batch = []

        # 1. Database connection pool & latency metrics
        try:
            from app.services.cluster.database_health import DatabaseHealthProvider
            provider = DatabaseHealthProvider(self.db)
            db_res = provider.check_health()
            lat = float(db_res.get("latency_ms", 0.0))
            batch.append({
                "metric_name": "database_latency_ms",
                "value": lat,
                "source": "database",
                "labels": {"component": "postgres_sqlite"}
            })
            pool_info = db_res.get("pool", {})
            if isinstance(pool_info, dict) and "size" in pool_info:
                batch.append({
                    "metric_name": "database_pool_size",
                    "value": float(pool_info["size"]),
                    "source": "database",
                    "labels": {"component": "pool"}
                })
        except Exception as e:
            logger.warning(f"Error gathering database metrics: {e}")

        # 2. Cluster & Distributed Queue metrics
        try:
            from app.models.cluster_v9_models import ClusterNode, DistributedJob
            total_nodes = self.db.scalar(select(func.count(ClusterNode.id))) or 0
            healthy_nodes = self.db.scalar(select(func.count(ClusterNode.id)).where(ClusterNode.status == "HEALTHY")) or 0
            pending_jobs = self.db.scalar(select(func.count(DistributedJob.id)).where(DistributedJob.status == "PENDING")) or 0
            running_jobs = self.db.scalar(select(func.count(DistributedJob.id)).where(DistributedJob.status == "RUNNING")) or 0

            batch.extend([
                {"metric_name": "cluster_node_total", "value": float(total_nodes), "source": "cluster", "labels": {}},
                {"metric_name": "cluster_node_healthy", "value": float(healthy_nodes), "source": "cluster", "labels": {}},
                {"metric_name": "scheduler_queue_depth", "value": float(pending_jobs), "source": "scheduler", "labels": {"state": "pending"}},
                {"metric_name": "scheduler_running_jobs", "value": float(running_jobs), "source": "scheduler", "labels": {"state": "running"}}
            ])
        except Exception as e:
            logger.warning(f"Error gathering cluster metrics: {e}")

        # 3. Agent Fleet metrics
        try:
            from app.models.client import Client
            total_clients = self.db.scalar(select(func.count(Client.id))) or 0
            batch.append({
                "metric_name": "agent_fleet_total",
                "value": float(total_clients),
                "source": "agent",
                "labels": {}
            })
        except Exception as e:
            logger.warning(f"Error gathering agent metrics: {e}")

        # 4. Storage Repositories & CAS metrics
        try:
            from app.models.storage_repository import StorageRepository
            from app.models.storage_object import StorageObject
            repos = list(self.db.scalars(select(StorageRepository)).all())
            total_cap = sum(r.capacity_bytes for r in repos if r.capacity_bytes)
            total_used = sum(r.used_bytes for r in repos if r.used_bytes)
            batch.extend([
                {"metric_name": "repository_count", "value": float(len(repos)), "source": "repository", "labels": {}},
                {"metric_name": "storage_total_capacity_bytes", "value": float(total_cap), "source": "storage", "labels": {}},
                {"metric_name": "storage_used_bytes", "value": float(total_used), "source": "storage", "labels": {}}
            ])

            cas_objects = self.db.scalar(select(func.count(StorageObject.id))) or 0
            cas_unique_bytes = self.db.scalar(select(func.sum(StorageObject.stored_size))) or 0
            batch.extend([
                {"metric_name": "cas_object_count", "value": float(cas_objects), "source": "cas", "labels": {}},
                {"metric_name": "cas_unique_bytes", "value": float(cas_unique_bytes), "source": "cas", "labels": {}}
            ])
        except Exception as e:
            logger.warning(f"Error gathering storage metrics: {e}")

        # 5. Security Engine metrics
        try:
            from app.models.security_v8_models import SecurityEvent, SecurityIncident
            sec_events = self.db.scalar(select(func.count(SecurityEvent.id))) or 0
            active_incidents = self.db.scalar(select(func.count(SecurityIncident.id)).where(SecurityIncident.status.notin_(["RESOLVED", "CLOSED"]))) or 0
            batch.extend([
                {"metric_name": "security_events_total", "value": float(sec_events), "source": "security", "labels": {}},
                {"metric_name": "security_active_incidents", "value": float(active_incidents), "source": "security", "labels": {}}
            ])
        except Exception as e:
            logger.warning(f"Error gathering security metrics: {e}")

        # Ingest all gathered samples
        count = self.record_metrics_batch(batch)
        return {
            "timestamp": now.isoformat(),
            "collected_samples_count": count,
            "metrics": {item["metric_name"]: item["value"] for item in batch}
        }
