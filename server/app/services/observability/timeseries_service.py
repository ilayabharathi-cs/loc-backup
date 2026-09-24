"""RetroVault V10 Time-Series Downsampling and Telemetry Retention Pruner.

Downsamples raw high-frequency telemetry samples into hourly and daily rollups
and prunes expired metrics and alert history while strictly protecting recovery
points, CAS blocks, security audit records, and compliance evidence.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List
from sqlalchemy import select, func, delete, and_
from sqlalchemy.orm import Session

from app.models.observability_v10_models import MetricSample, OperationalAlert, OperationalIncident

logger = logging.getLogger(__name__)


class TimeseriesService:
    """Manages metric rollup aggregations and data lifecycle retention policies."""

    def __init__(self, db: Session):
        self.db = db

    def downsample_metrics(self, hours_back: int = 24) -> Dict[str, int]:
        """Aggregate RAW metrics older than 1 hour into HOURLY summaries."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=1)
        start_cutoff = now - timedelta(hours=hours_back)

        # Select unique metric_name, source, and hourly buckets
        stmt = (
            select(
                MetricSample.metric_name,
                MetricSample.source,
                func.count(MetricSample.id).label("cnt"),
                func.min(MetricSample.value).label("min_v"),
                func.max(MetricSample.value).label("max_v"),
                func.sum(MetricSample.value).label("sum_v"),
                func.avg(MetricSample.value).label("avg_v"),
            )
            .where(
                MetricSample.granularity == "RAW",
                MetricSample.timestamp >= start_cutoff,
                MetricSample.timestamp <= cutoff
            )
            .group_by(MetricSample.metric_name, MetricSample.source)
        )

        rows = self.db.execute(stmt).all()
        aggregated_count = 0

        for r in rows:
            if not r.cnt:
                continue
            hourly_sample = MetricSample(
                metric_name=r.metric_name,
                value=float(r.avg_v),
                timestamp=cutoff,
                source=r.source,
                labels_json=None,
                granularity="HOURLY",
                sample_count=int(r.cnt),
                min_value=float(r.min_v),
                max_value=float(r.max_v),
                sum_value=float(r.sum_v)
            )
            self.db.add(hourly_sample)
            aggregated_count += 1

        self.db.commit()
        return {"hourly_buckets_created": aggregated_count}

    def prune_telemetry(
        self,
        raw_metric_retention_days: int = 30,
        aggregate_retention_days: int = 365,
        alert_retention_days: int = 90,
        incident_retention_days: int = 365
    ) -> Dict[str, Any]:
        """Clean up old metric samples and operational alerts beyond retention thresholds.
        
        SAFETY INVARIANT:
        This operation ONLY touches `metric_samples`, `operational_alerts`, and `operational_incidents`.
        It NEVER touches `recovery_points`, `storage_objects`, `audit_logs`, `security_events`,
        or `compliance_evidence`.
        """
        now = datetime.now(timezone.utc)

        raw_cutoff = now - timedelta(days=raw_metric_retention_days)
        agg_cutoff = now - timedelta(days=aggregate_retention_days)
        alert_cutoff = now - timedelta(days=alert_retention_days)
        incident_cutoff = now - timedelta(days=incident_retention_days)

        # 1. Prune RAW metrics
        del_raw = self.db.execute(
            delete(MetricSample).where(
                MetricSample.granularity == "RAW",
                MetricSample.timestamp < raw_cutoff
            )
        ).rowcount

        # 2. Prune aggregated metrics
        del_agg = self.db.execute(
            delete(MetricSample).where(
                MetricSample.granularity.in_(["HOURLY", "DAILY", "MONTHLY"]),
                MetricSample.timestamp < agg_cutoff
            )
        ).rowcount

        # 3. Prune resolved alerts older than retention period
        del_alerts = self.db.execute(
            delete(OperationalAlert).where(
                OperationalAlert.status == "RESOLVED",
                OperationalAlert.resolved_at < alert_cutoff
            )
        ).rowcount

        # 4. Prune closed incidents older than retention period
        del_incidents = self.db.execute(
            delete(OperationalIncident).where(
                OperationalIncident.status.in_(["RESOLVED", "CLOSED"]),
                OperationalIncident.created_at < incident_cutoff
            )
        ).rowcount

        self.db.commit()

        logger.info(
            f"Telemetry retention cleanup: raw={del_raw}, agg={del_agg}, "
            f"alerts={del_alerts}, incidents={del_incidents}"
        )

        return {
            "pruned_raw_metrics": del_raw,
            "pruned_aggregated_metrics": del_agg,
            "pruned_resolved_alerts": del_alerts,
            "pruned_closed_incidents": del_incidents,
            "protected_domains": [
                "recovery_points",
                "storage_objects",
                "audit_logs",
                "security_events",
                "compliance_evidence"
            ]
        }
