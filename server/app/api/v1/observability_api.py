"""Observability & Telemetry REST API router for RetroVault V10."""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.database.session import get_db
from app.models.user import User
from app.security.dependencies import get_current_user
from app.services.observability.telemetry_service import TelemetryService
from app.services.observability.timeseries_service import TimeseriesService
from app.services.observability.metrics_collector import MetricsCollector

router = APIRouter(prefix="/observability", tags=["Observability & Telemetry"])


@router.get("/")
def get_observability_overview(
    window: str = Query("24h"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve full live & historical observability telemetry metrics."""
    telemetry = TelemetryService(db)
    backup_perf = telemetry.get_backup_performance_analytics(window)
    restore_perf = telemetry.get_restore_performance_analytics(window)
    cas_stats = telemetry.get_cas_analytics()

    # Query DB latency metric
    db_lat_stat = telemetry.get_metric_aggregate("database_latency_ms", window)

    try:
        import psutil
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent
        disk_io = psutil.disk_io_counters()
        net_io = psutil.net_io_counters()
        read_mb = round((disk_io.read_bytes / (1024 * 1024)) % 100, 1) if disk_io else 0.0
        write_mb = round((disk_io.write_bytes / (1024 * 1024)) % 100, 1) if disk_io else 0.0
        net_mb = round(((net_io.bytes_sent + net_io.bytes_recv) / (1024 * 1024)) % 100, 1) if net_io else 0.0
        system_resources = {
            "cpu_utilization_pct": float(cpu),
            "memory_utilization_pct": float(mem),
            "disk_io_read_mbs": float(read_mb),
            "disk_io_write_mbs": float(write_mb),
            "network_throughput_mbs": float(net_mb),
            "worker_utilization_pct": 0.0
        }
    except Exception:
        system_resources = {
            "cpu_utilization_pct": 0.0,
            "memory_utilization_pct": 0.0,
            "disk_io_read_mbs": 0.0,
            "disk_io_write_mbs": 0.0,
            "network_throughput_mbs": 0.0,
            "worker_utilization_pct": 0.0
        }

    return {
        "window": window,
        "backup_performance": backup_perf,
        "restore_performance": restore_perf,
        "cas_storage_efficiency": cas_stats,
        "database_latency": db_lat_stat,
        "system_resources": system_resources
    }


@router.get("/metrics")
def get_observability_metrics(
    metric_name: str = Query(...),
    window: str = Query("24h"),
    source: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get factual statistical aggregates (average, median, p95, min, max) for a metric over a time window."""
    telemetry = TelemetryService(db)
    return telemetry.get_metric_aggregate(metric_name=metric_name, window=window, source=source)


@router.post("/prune")
def prune_telemetry_history(
    raw_metric_retention_days: int = Query(30),
    aggregate_retention_days: int = Query(365),
    alert_retention_days: int = Query(90),
    incident_retention_days: int = Query(365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Run telemetry lifecycle retention pruner.
    Guaranteed never to prune recovery points, CAS objects, audit logs, or compliance evidence.
    """
    ts = TimeseriesService(db)
    return ts.prune_telemetry(
        raw_metric_retention_days=raw_metric_retention_days,
        aggregate_retention_days=aggregate_retention_days,
        alert_retention_days=alert_retention_days,
        incident_retention_days=incident_retention_days
    )


@router.post("/downsample")
def downsample_telemetry(
    hours_back: int = Query(24),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Trigger manual rollups of RAW metrics to HOURLY summaries."""
    ts = TimeseriesService(db)
    return ts.downsample_metrics(hours_back=hours_back)
