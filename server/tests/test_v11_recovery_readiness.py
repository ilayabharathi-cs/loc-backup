"""Tests for RetroVault V11 Factual Recovery Readiness Calculation."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlalchemy import select

from app.database.session import SessionLocal
from app.models.workload_v11_models import Workload
from app.services.workload.readiness_engine import (
    RecoveryReadinessEngine,
    READINESS_READY,
    READINESS_DEGRADED,
    READINESS_NOT_READY,
    READINESS_UNKNOWN
)


def test_factual_recovery_readiness_signals():
    db = SessionLocal()
    try:
        engine = RecoveryReadinessEngine(db)

        # 1. Non-existent workload evaluation -> UNKNOWN
        missing_res = engine.evaluate_workload_readiness("non-existent-workload-xyz")
        assert missing_res["readiness_state"] == READINESS_UNKNOWN

        # 2. Existing workload evaluation
        w_stmt = select(Workload).order_by(Workload.id.desc())
        workload = db.execute(w_stmt).scalars().first()
        if workload:
            readiness = engine.evaluate_workload_readiness(workload.workload_id)
            assert readiness["readiness_state"] in [READINESS_READY, READINESS_DEGRADED, READINESS_NOT_READY]
            assert "contributing_signals" in readiness
            assert "rpo_compliance_percent" in readiness
            # Signals must be transparently explainable
            assert "blocking_factors" in readiness
            assert "degrading_factors" in readiness

    finally:
        db.close()
