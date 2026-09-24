"""Tests for RetroVault V11 Backup Chain Validation Engine."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json
import uuid
import datetime
from sqlalchemy import select

from app.database.session import SessionLocal
from app.models.workload_v11_models import BackupChain, WorkloadArtifact
from app.models.recovery_point import RecoveryPoint
from app.models.storage_object import StorageObject
from app.services.workload.backup_chain_validator import BackupChainValidator


def test_backup_chain_validation_states():
    db = SessionLocal()
    try:
        validator = BackupChainValidator(db)

        # 1. Fetch or create a valid chain
        stmt = select(BackupChain).order_by(BackupChain.id.desc())
        chain = db.execute(stmt).scalars().first()
        if not chain:
            # Create a mock chain
            rp_stmt = select(RecoveryPoint).order_by(RecoveryPoint.id.desc())
            rp = db.execute(rp_stmt).scalars().first()
            rp_id = str(rp.id) if rp else "1"
            chain = BackupChain(
                chain_id=f"chain-test-{uuid.uuid4().hex[:6]}",
                workload_id="test-workload-val",
                base_recovery_point_id=rp_id,
                latest_recovery_point_id=rp_id,
                chain_length=1,
                status="VALID"
            )
            db.add(chain)
            db.commit()

        # Validate healthy chain
        val_res = validator.validate_chain(chain.chain_id)
        assert val_res["status"] in ["VALID", "DEGRADED"]
        assert val_res["chain_id"] == chain.chain_id

        # 2. Test broken chain detection (invalid non-existent base RP)
        broken_chain = BackupChain(
            chain_id=f"chain-broken-{uuid.uuid4().hex[:6]}",
            workload_id="test-workload-broken",
            base_recovery_point_id="999999",  # Non-existent
            latest_recovery_point_id="999999",
            chain_length=1,
            status="VALID"
        )
        db.add(broken_chain)
        db.commit()

        broken_res = validator.validate_chain(broken_chain.chain_id)
        assert broken_res["status"] == "BROKEN"
        assert "missing or deleted" in broken_res["broken_reason"]

        # 3. Non-existent chain lookup returns UNKNOWN
        missing_res = validator.validate_chain("non-existent-chain-xyz")
        assert missing_res["status"] == "UNKNOWN"

    finally:
        db.close()
