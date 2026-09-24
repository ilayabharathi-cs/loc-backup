"""Tests for RetroVault V11 Synthetic Recovery and Restore Verification."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json
from sqlalchemy import select

from app.database.session import SessionLocal
from app.models.recovery_point import RecoveryPoint
from app.models.workload_v11_models import RecoveryVerification, Workload
from app.services.workload.recovery_verification import RecoveryVerificationEngine


def test_synthetic_restore_verification_pipeline():
    db = SessionLocal()
    try:
        engine = RecoveryVerificationEngine(db)

        # 1. Fetch RP and Workload
        rp_stmt = select(RecoveryPoint).order_by(RecoveryPoint.id.desc())
        rp = db.execute(rp_stmt).scalars().first()
        rp_id = str(rp.id) if rp else "1"

        w_stmt = select(Workload).order_by(Workload.id.desc())
        w = db.execute(w_stmt).scalars().first()
        workload_id = w.workload_id if w else "test-workload"

        # 2. Trigger and Execute Verification
        verif = engine.trigger_verification(
            recovery_point_id=rp_id,
            workload_id=workload_id,
            verification_type="CHECKSUM",
            initiated_by="UNIT_TEST"
        )
        assert verif.verification_id is not None
        assert verif.status == "PENDING"

        exec_res = engine.execute_verification(verif.verification_id)
        assert exec_res["success"] is True
        assert exec_res["status"] == "VERIFIED"
        assert exec_res["duration_ms"] >= 0

        # Verify steps were recorded
        db.refresh(verif)
        assert len(verif.steps) >= 1
        assert all(step.status == "PASSED" for step in verif.steps)

        # Invariant: Sandbox path must be cleaned up after execution
        assert not os.path.exists(verif.sandbox_path)

        # 3. Test verification retry
        retry_verif = engine.trigger_verification(
            recovery_point_id=rp_id,
            workload_id=workload_id,
            verification_type="MANIFEST",
            initiated_by="RETRY_TEST"
        )
        retry_res = engine.execute_verification(retry_verif.verification_id)
        assert retry_res["success"] is True

    finally:
        db.close()
