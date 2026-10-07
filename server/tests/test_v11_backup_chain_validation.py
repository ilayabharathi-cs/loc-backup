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

        # 1. Create a dedicated valid chain and recovery point
        rp = RecoveryPoint(
            client_id=1,
            backup_run_id=1,
            backup_type="full",
            status="valid",
            timestamp=datetime.datetime.now(datetime.timezone.utc),
            files_count=1,
            total_size_bytes=100
        )
        db.add(rp)
        db.commit()
        db.refresh(rp)

        chain = BackupChain(
            chain_id=f"chain-valid-{uuid.uuid4().hex[:6]}",
            workload_id=f"workload-valid-{uuid.uuid4().hex[:6]}",
            base_recovery_point_id=str(rp.id),
            latest_recovery_point_id=str(rp.id),
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
        try:
            db.query(BackupChain).filter(BackupChain.workload_id.in_(["test-workload-val", "test-workload-broken"])).delete()
            db.commit()
        except Exception:
            pass
        db.close()
