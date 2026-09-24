"""Capacity Planning & Forecasting REST API router for RetroVault V10."""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database.session import get_db
from app.models.user import User
from app.models.storage_repository import StorageRepository
from app.security.dependencies import get_current_user
from app.schemas.v10_schemas import (
    CapacitySnapshotResponse,
    CapacityForecastRequest,
    CapacityForecastResponse
)
from app.services.observability.capacity_service import CapacityPlanningService

router = APIRouter(prefix="/capacity", tags=["Capacity Planning"])


@router.get("/")
def get_capacity_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve capacity utilization, free space, and growth across all repositories."""
    repos = list(db.scalars(select(StorageRepository)).all())
    cap_service = CapacityPlanningService(db)

    results = []
    total_capacity = 0
    total_used = 0
    total_free = 0

    for r in repos:
        cap = r.capacity_bytes or (100 * 1024 * 1024 * 1024)
        used = r.used_bytes or 0
        free = max(0, cap - used)
        util = round((used / cap) * 100.0, 2) if cap > 0 else 0.0

        total_capacity += cap
        total_used += used
        total_free += free

        results.append({
            "repository_id": r.id,
            "name": r.name,
            "path": r.path,
            "status": getattr(r, "status", "ONLINE"),
            "capacity_bytes": cap,
            "used_bytes": used,
            "free_bytes": free,
            "utilization_pct": util,
            "dedup_ratio": 1.0,
            "compression_ratio": 1.0,
            "physical_savings_bytes": 0
        })

    overall_util = round((total_used / total_capacity) * 100.0, 2) if total_capacity > 0 else 0.0

    return {
        "total_repositories": len(repos),
        "total_capacity_bytes": total_capacity,
        "total_used_bytes": total_used,
        "total_free_bytes": total_free,
        "overall_utilization_pct": overall_util,
        "repositories": results
    }


@router.post("/snapshots/{repo_id}", response_model=CapacitySnapshotResponse)
def take_capacity_snapshot(
    repo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Take an on-demand capacity snapshot for a storage repository."""
    cap_service = CapacityPlanningService(db)
    try:
        snap = cap_service.take_repository_snapshot(repo_id)
        return CapacitySnapshotResponse(
            repository_id=snap.repository_id,
            logical_bytes=snap.logical_bytes,
            unique_content_bytes=snap.unique_content_bytes,
            compressed_bytes=snap.compressed_bytes,
            physical_bytes=snap.physical_bytes,
            free_bytes=snap.free_bytes,
            total_capacity_bytes=snap.total_capacity_bytes,
            utilization_pct=snap.utilization_pct,
            dedup_ratio=snap.dedup_ratio,
            compression_ratio=snap.compression_ratio,
            overall_efficiency=snap.overall_efficiency,
            timestamp=snap.timestamp.isoformat()
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/forecast", response_model=CapacityForecastResponse)
def get_capacity_forecast(
    repository_id: int = Query(...),
    window_days: int = Query(30),
    method: str = Query("linear_trend"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate mathematical storage exhaustion forecast (returns INSUFFICIENT_DATA if <3 samples exist)."""
    cap_service = CapacityPlanningService(db)
    res = cap_service.calculate_forecast(repository_id, window_days=window_days, method=method)
    return CapacityForecastResponse(**res)


@router.post("/forecast", response_model=CapacityForecastResponse)
def post_capacity_forecast(
    payload: CapacityForecastRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Trigger mathematical capacity projection calculation."""
    cap_service = CapacityPlanningService(db)
    res = cap_service.calculate_forecast(
        payload.repository_id,
        window_days=payload.window_days,
        method=payload.method
    )
    return CapacityForecastResponse(**res)
