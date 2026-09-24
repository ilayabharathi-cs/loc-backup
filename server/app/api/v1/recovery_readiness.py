"""Recovery Readiness REST API router for RetroVault V11."""

import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database.session import get_db
from app.models.user import User
from app.models.workload_v11_models import RecoveryReadiness, Workload
from app.security.dependencies import get_current_user
from app.services.workload.readiness_engine import RecoveryReadinessEngine

router = APIRouter(prefix="/recovery-readiness", tags=["Recovery Readiness"])


@router.get("/")
def get_all_readiness(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve recovery readiness evaluation for all workloads."""
    stmt = select(Workload)
    workloads = db.execute(stmt).scalars().all()

    engine = RecoveryReadinessEngine(db)
    results = []
    for w in workloads:
        res = engine.evaluate_workload_readiness(w.workload_id)
        results.append(res)
    return results


@router.get("/{workload_id}")
def get_workload_readiness(
    workload_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Evaluate factual recovery readiness for a specific workload."""
    engine = RecoveryReadinessEngine(db)
    res = engine.evaluate_workload_readiness(workload_id)
    if res.get("readiness_state") == "UNKNOWN" and "error" in res.get("contributing_signals", {}):
        raise HTTPException(status_code=404, detail=res["contributing_signals"]["error"])
    return res
