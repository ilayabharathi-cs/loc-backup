"""Tests for RetroVault V10 Metrics Collection, Downsampling & Telemetry Pruning."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import datetime
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database.session import SessionLocal
from app.services.observability.metrics_collector import MetricsCollector
from app.services.observability.telemetry_service import TelemetryService
from app.services.observability.timeseries_service import TimeseriesService
from app.models.observability_v10_models import MetricSample

client = TestClient(app)


@pytest.fixture
def auth_headers():
    res = client.post("/api/v1/auth/login", json={"username": "admin", "password": "AdminPass123!"})
    token = res.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_metrics_collection_and_batching():
    db = SessionLocal()
    try:
        collector = MetricsCollector(db)

        # 1. Single sample
        s1 = collector.record_metric(
            metric_name="backup_cpu_load",
            value=45.2,
            source="worker",
            labels={"node": "node-1"}
        )
        assert s1.id is not None
        assert s1.metric_name == "backup_cpu_load"
        assert s1.value == 45.2

        # 2. Batch sample
        count = collector.record_metrics_batch([
            {"metric_name": "agent_heartbeat_latency", "value": 12.4, "source": "agent", "labels": {"client": "c1"}},
            {"metric_name": "agent_heartbeat_latency", "value": 14.1, "source": "agent", "labels": {"client": "c2"}},
            {"metric_name": "network_transfer_rate", "value": 85.5, "source": "network", "labels": {}},
        ])
        assert count == 3

        # 3. Query
        queried = collector.query_metrics(metric_name="agent_heartbeat_latency")
        assert len(queried) >= 2

        # 4. Live system metrics collection
        live_res = collector.collect_live_system_metrics()
        assert "metrics" in live_res
        assert live_res["collected_samples_count"] > 0
    finally:
        db.close()


def test_telemetry_aggregations_and_cas_analytics():
    db = SessionLocal()
    try:
        collector = MetricsCollector(db)
        # Ingest several samples
        for val in [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]:
            collector.record_metric("test_latency_ms", val, "api")

        telemetry = TelemetryService(db)
        agg = telemetry.get_metric_aggregate("test_latency_ms", "24h")
        assert agg["sample_count"] >= 10
        assert agg["min"] <= 10.0
        assert agg["max"] >= 100.0
        assert agg["average"] > 0
        assert agg["p95"] >= 90.0

        cas_res = telemetry.get_cas_analytics()
        assert "dedup_ratio" in cas_res
        assert "compression_ratio" in cas_res
        assert "overall_efficiency" in cas_res
    finally:
        db.close()


def test_timeseries_downsampling_and_pruning():
    db = SessionLocal()
    try:
        ts = TimeseriesService(db)

        # 1. Downsample
        downsample_res = ts.downsample_metrics(hours_back=48)
        assert "hourly_buckets_created" in downsample_res

        # 2. Prune telemetry with safety guardrails
        prune_res = ts.prune_telemetry(
            raw_metric_retention_days=1,
            aggregate_retention_days=30,
            alert_retention_days=1,
            incident_retention_days=1
        )
        assert "pruned_raw_metrics" in prune_res
        assert "protected_domains" in prune_res
        assert "recovery_points" in prune_res["protected_domains"]
        assert "compliance_evidence" in prune_res["protected_domains"]
    finally:
        db.close()


def test_observability_rest_api(auth_headers):
    # 1. Observability Overview
    res = client.get("/api/v1/observability/?window=24h", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "system_resources" in data
    assert "cas_storage_efficiency" in data
    assert "backup_performance" in data
    assert "restore_performance" in data

    # 2. Metric aggregate query
    res2 = client.get("/api/v1/observability/metrics?metric_name=test_latency_ms&window=24h", headers=auth_headers)
    assert res2.status_code == 200
    assert "p95" in res2.json()

    # 3. Post downsample
    res3 = client.post("/api/v1/observability/downsample?hours_back=24", headers=auth_headers)
    assert res3.status_code == 200

    # 4. Post prune
    res4 = client.post("/api/v1/observability/prune", headers=auth_headers)
    assert res4.status_code == 200
    assert "protected_domains" in res4.json()
