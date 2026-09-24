"""RetroVault V10 Telemetry & Aggregation Service.

Calculates factual statistical aggregates (average, median, p95, min, max)
over standardized time windows (1h, 6h, 24h, 7d, 30d, 90d), throughput metrics,
and CAS storage efficiency metrics.
"""

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session

from app.models.observability_v10_models import MetricSample
from app.models.backup_run import BackupRun
from app.models.restore_job import RestoreJob
from app.models.storage_object import StorageObject
from app.models.storage_repository import StorageRepository


TIME_WINDOWS = {
    "1h": timedelta(hours=1),
    "6h": timedelta(hours=6),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
    "90d": timedelta(days=90),
}


def calculate_percentile(values: List[float], percentile: float) -> float:
    """Calculate percentile from a sorted list of float values using linear interpolation."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * (percentile / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(sorted_vals[int(k)])
    d0 = sorted_vals[int(f)] * (c - k)
    d1 = sorted_vals[int(c)] * (k - f)
    return float(d0 + d1)


class TelemetryService:
    """Service providing factual statistical telemetry and performance analytics."""

    def __init__(self, db: Session):
        self.db = db

    def get_metric_aggregate(
        self,
        metric_name: str,
        window: str = "24h",
        source: Optional[str] = None
    ) -> Dict[str, Any]:
        """Compute statistical summary for a metric over a given time window."""
        delta = TIME_WINDOWS.get(window, timedelta(hours=24))
        cutoff = datetime.now(timezone.utc) - delta

        stmt = select(MetricSample.value).where(
            MetricSample.metric_name == metric_name,
            MetricSample.timestamp >= cutoff
        )
        if source:
            stmt = stmt.where(MetricSample.source == source)

        values = [float(v) for v in self.db.scalars(stmt).all()]
        if not values:
            return {
                "metric_name": metric_name,
                "window": window,
                "sample_count": 0,
                "min": 0.0,
                "max": 0.0,
                "average": 0.0,
                "median": 0.0,
                "p95": 0.0
            }

        avg_val = sum(values) / len(values)
        return {
            "metric_name": metric_name,
            "window": window,
            "sample_count": len(values),
            "min": float(min(values)),
            "max": float(max(values)),
            "average": float(round(avg_val, 4)),
            "median": float(round(calculate_percentile(values, 50.0), 4)),
            "p95": float(round(calculate_percentile(values, 95.0), 4))
        }

    def get_backup_performance_analytics(self, window: str = "24h") -> Dict[str, Any]:
        """Aggregate backup run metrics (duration, throughput, files, bytes, dedup) over time window."""
        delta = TIME_WINDOWS.get(window, timedelta(hours=24))
        cutoff = datetime.now(timezone.utc) - delta

        runs = list(self.db.scalars(
            select(BackupRun).where(BackupRun.started_at >= cutoff)
        ).all())

        durations = []
        logical_bytes = []
        uploaded_bytes = []
        dedup_ratios = []
        files_scanned = []
        files_changed = []

        for r in runs:
            # calculate duration if started and completed
            if r.started_at and r.completed_at:
                dur = (r.completed_at - r.started_at).total_seconds()
                if dur > 0:
                    durations.append(dur)
            if hasattr(r, "bytes_total") and r.bytes_total is not None:
                logical_bytes.append(float(r.bytes_total))
            if hasattr(r, "bytes_uploaded") and r.bytes_uploaded is not None:
                uploaded_bytes.append(float(r.bytes_uploaded))
            if hasattr(r, "files_processed") and r.files_processed is not None:
                files_scanned.append(float(r.files_processed))
            if hasattr(r, "files_modified") and r.files_modified is not None:
                files_changed.append(float(r.files_modified))

        return {
            "window": window,
            "total_runs": len(runs),
            "duration_seconds": self._stats(durations),
            "logical_bytes": self._stats(logical_bytes),
            "uploaded_bytes": self._stats(uploaded_bytes),
            "dedup_ratio": self._stats(dedup_ratios),
            "files_scanned": self._stats(files_scanned),
            "files_changed": self._stats(files_changed),
        }

    def get_restore_performance_analytics(self, window: str = "24h") -> Dict[str, Any]:
        """Aggregate restore run metrics (duration, bytes restored, files, throughput) over time window."""
        delta = TIME_WINDOWS.get(window, timedelta(hours=24))
        cutoff = datetime.now(timezone.utc) - delta

        jobs = list(self.db.scalars(
            select(RestoreJob).where(RestoreJob.created_at >= cutoff)
        ).all())

        durations = []
        bytes_restored = []
        files_restored = []
        throughputs_mb_s = []

        for j in jobs:
            dur = 0.0
            if j.started_at and j.completed_at:
                dur = (j.completed_at - j.started_at).total_seconds()
                if dur > 0:
                    durations.append(dur)
            b = float(j.restored_bytes or 0)
            f = float(j.completed_files or 0)
            bytes_restored.append(b)
            files_restored.append(f)
            if dur > 0 and b > 0:
                throughputs_mb_s.append((b / (1024.0 * 1024.0)) / dur)

        return {
            "window": window,
            "total_restores": len(jobs),
            "duration_seconds": self._stats(durations),
            "bytes_restored": self._stats(bytes_restored),
            "files_restored": self._stats(files_restored),
            "throughput_mb_s": self._stats(throughputs_mb_s),
        }

    def get_cas_analytics(self) -> Dict[str, Any]:
        """Aggregate Content Addressable Storage (CAS) efficiency metrics across all repositories."""
        # Query total logical bytes from all backup files
        from app.models.backup_file import BackupFile
        logical_bytes = self.db.scalar(select(func.sum(BackupFile.size_bytes))) or 0
        total_files = self.db.scalar(select(func.count(BackupFile.id))) or 0

        # Query unique stored bytes from storage objects
        unique_bytes = self.db.scalar(select(func.sum(StorageObject.stored_size))) or 0
        unique_objects = self.db.scalar(select(func.count(StorageObject.id))) or 0

        # Physical repository bytes
        repos = list(self.db.scalars(select(StorageRepository)).all())
        physical_bytes = sum(r.used_bytes for r in repos if r.used_bytes)

        # Reproducible calculations
        dedup_ratio = round(logical_bytes / unique_bytes, 2) if unique_bytes > 0 else 1.0
        compression_ratio = round(unique_bytes / physical_bytes, 2) if physical_bytes > 0 and unique_bytes > 0 else 1.0
        overall_efficiency = round(logical_bytes / physical_bytes, 2) if physical_bytes > 0 else 1.0
        dedup_savings_bytes = max(0, logical_bytes - unique_bytes)
        physical_savings_bytes = max(0, logical_bytes - physical_bytes)

        return {
            "logical_bytes": logical_bytes,
            "logical_files": total_files,
            "unique_bytes": unique_bytes,
            "unique_objects": unique_objects,
            "physical_bytes": physical_bytes,
            "dedup_ratio": float(dedup_ratio),
            "compression_ratio": float(compression_ratio),
            "overall_efficiency": float(overall_efficiency),
            "dedup_savings_bytes": dedup_savings_bytes,
            "physical_savings_bytes": physical_savings_bytes
        }

    def _stats(self, values: List[float]) -> Dict[str, float]:
        if not values:
            return {"count": 0, "min": 0.0, "max": 0.0, "average": 0.0, "median": 0.0, "p95": 0.0}
        avg_val = sum(values) / len(values)
        return {
            "count": len(values),
            "min": float(round(min(values), 2)),
            "max": float(round(max(values), 2)),
            "average": float(round(avg_val, 2)),
            "median": float(round(calculate_percentile(values, 50.0), 2)),
            "p95": float(round(calculate_percentile(values, 95.0), 2))
        }
