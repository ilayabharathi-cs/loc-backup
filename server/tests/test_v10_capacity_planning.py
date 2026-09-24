"""Tests for RetroVault V10 Capacity Planning & Mathematical Forecasting."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import datetime
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database.session import SessionLocal
from app.models.storage_repository import StorageRepository
from app.models.observability_v10_models import CapacitySnapshot
from app.services.observability.capacity_service import CapacityPlanningService

client = TestClient(app)


@pytest.fixture
def auth_headers():
    res = client.post("/api/v1/auth/login", json={"username": "admin", "password": "AdminPass123!"})
    token = res.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_capacity_service_and_insufficient_data():
    db = SessionLocal()
    try:
        # Create or fetch repository
        repo = db.query(StorageRepository).first()
        if not repo:
            repo = StorageRepository(
                name="cap-test-repo",
                path="./tmp_repo",
                capacity_bytes=500 * 1024 * 1024 * 1024,
                used_bytes=100 * 1024 * 1024 * 1024
            )
            db.add(repo)
            db.commit()
            db.refresh(repo)

        cap_service = CapacityPlanningService(db)

        # 1. Take snapshot
        snap = cap_service.take_repository_snapshot(repo.id)
        assert snap.id is not None
        assert snap.repository_id == repo.id

        # 2. If <3 snapshots, forecast must return INSUFFICIENT_DATA
        # Clean up any snapshots beyond 1 for this test
        db.query(CapacitySnapshot).filter(CapacitySnapshot.repository_id == repo.id).delete()
        db.commit()

        snap1 = cap_service.take_repository_snapshot(repo.id)
        res_insufficient = cap_service.calculate_forecast(repo.id)
        assert res_insufficient["status"] == "INSUFFICIENT_DATA"
        assert res_insufficient["sample_count"] < 3
        assert res_insufficient["is_projection"] is True

        # 3. Create at least 3 historical snapshots spaced across days
        now = datetime.datetime.now(datetime.timezone.utc)
        snap2 = CapacitySnapshot(
            repository_id=repo.id,
            timestamp=now - datetime.timedelta(days=2),
            logical_bytes=80 * 1024 * 1024 * 1024,
            unique_content_bytes=80 * 1024 * 1024 * 1024,
            compressed_bytes=80 * 1024 * 1024 * 1024,
            physical_bytes=80 * 1024 * 1024 * 1024,
            free_bytes=420 * 1024 * 1024 * 1024,
            total_capacity_bytes=500 * 1024 * 1024 * 1024
        )
        snap3 = CapacitySnapshot(
            repository_id=repo.id,
            timestamp=now - datetime.timedelta(days=1),
            logical_bytes=90 * 1024 * 1024 * 1024,
            unique_content_bytes=90 * 1024 * 1024 * 1024,
            compressed_bytes=90 * 1024 * 1024 * 1024,
            physical_bytes=90 * 1024 * 1024 * 1024,
            free_bytes=410 * 1024 * 1024 * 1024,
            total_capacity_bytes=500 * 1024 * 1024 * 1024
        )
        db.add_all([snap2, snap3])
        db.commit()

        # 4. Now calculate forecast with >=3 points
        res_forecast = cap_service.calculate_forecast(repo.id)
        assert res_forecast["status"] == "PROJECTED"
        assert res_forecast["is_projection"] is True
        assert res_forecast["sample_count"] >= 3
        assert "daily_burn_rate_bytes" in res_forecast
        assert "forecast_7d_bytes" in res_forecast
        assert "forecast_30d_bytes" in res_forecast
        assert "forecast_90d_bytes" in res_forecast
        assert "disclaimer" in res_forecast
    finally:
        db.close()


def test_capacity_rest_api(auth_headers):
    # 1. Capacity overview
    res = client.get("/api/v1/capacity/", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "total_repositories" in data
    assert "repositories" in data

    if data["repositories"]:
        repo_id = data["repositories"][0]["repository_id"]
        # 2. Take on-demand snapshot
        s_res = client.post(f"/api/v1/capacity/snapshots/{repo_id}", headers=auth_headers)
        assert s_res.status_code == 200

        # 3. Forecast query
        f_res = client.get(f"/api/v1/capacity/forecast?repository_id={repo_id}", headers=auth_headers)
        assert f_res.status_code == 200
        assert f_res.json()["status"] in ["PROJECTED", "INSUFFICIENT_DATA"]
