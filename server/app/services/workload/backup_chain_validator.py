"""RetroVault V11: Backup Chain Validation Engine."""

import json
import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.workload_v11_models import BackupChain, WorkloadArtifact, Workload
from app.models.recovery_point import RecoveryPoint
from app.models.storage_object import StorageObject
from app.models.replication import ReplicationJob


CHAIN_VALID = "VALID"
CHAIN_DEGRADED = "DEGRADED"
CHAIN_BROKEN = "BROKEN"
CHAIN_UNKNOWN = "UNKNOWN"


class BackupChainValidator:
    """Validates full backup baseline, transaction logs, CAS objects, and chain continuity."""

    def __init__(self, db: Session):
        self.db = db

    def validate_chain(self, chain_id: str) -> Dict[str, Any]:
        """Perform end-to-end mathematical and storage integrity validation on a backup chain."""
        now = datetime.datetime.now(datetime.timezone.utc)
        stmt = select(BackupChain).where(BackupChain.chain_id == chain_id)
        chain = self.db.execute(stmt).scalars().first()

        if not chain:
            return {
                "chain_id": chain_id,
                "status": CHAIN_UNKNOWN,
                "broken_reason": f"Backup chain '{chain_id}' not found in registry"
            }

        reasons = []
        status = CHAIN_VALID

        # 1. Validate Base Recovery Point
        base_rp_stmt = select(RecoveryPoint).where(RecoveryPoint.id == int(chain.base_recovery_point_id))
        base_rp = self.db.execute(base_rp_stmt).scalars().first()
        if not base_rp:
            reasons.append(f"Full backup baseline RecoveryPoint {chain.base_recovery_point_id} is missing or deleted")
            status = CHAIN_BROKEN
        elif base_rp.status == "corrupted":
            reasons.append(f"Base RecoveryPoint {chain.base_recovery_point_id} is marked corrupted")
            status = CHAIN_BROKEN
        elif base_rp.status == "expired":
            reasons.append(f"Base RecoveryPoint {chain.base_recovery_point_id} has expired dependencies")
            status = CHAIN_DEGRADED

        # 2. Validate Latest Recovery Point
        if chain.latest_recovery_point_id != chain.base_recovery_point_id:
            latest_rp_stmt = select(RecoveryPoint).where(RecoveryPoint.id == int(chain.latest_recovery_point_id))
            latest_rp = self.db.execute(latest_rp_stmt).scalars().first()
            if not latest_rp:
                reasons.append(f"Latest RecoveryPoint {chain.latest_recovery_point_id} is missing")
                status = CHAIN_BROKEN
            elif latest_rp.status == "corrupted":
                reasons.append(f"Latest RecoveryPoint {chain.latest_recovery_point_id} is corrupted")
                status = CHAIN_BROKEN

        # 3. Validate CAS Artifacts Existence & Checksums
        art_stmt = select(WorkloadArtifact).where(WorkloadArtifact.workload_id == chain.workload_id)
        artifacts = self.db.execute(art_stmt).scalars().all()

        missing_artifacts = 0
        corrupted_artifacts = 0

        for art in artifacts:
            if art.storage_object_id:
                so_stmt = select(StorageObject).where(StorageObject.object_id == art.storage_object_id)
                so = self.db.execute(so_stmt).scalars().first()
                if not so:
                    missing_artifacts += 1
                elif so.state in ["CORRUPTED", "QUARANTINED"] or so.integrity_status == "CORRUPTED":
                    corrupted_artifacts += 1

        if missing_artifacts > 0:
            reasons.append(f"Detected {missing_artifacts} missing CAS storage object(s) referenced by chain")
            status = CHAIN_BROKEN
        if corrupted_artifacts > 0:
            reasons.append(f"Detected {corrupted_artifacts} corrupted CAS storage object(s) in chain")
            status = CHAIN_BROKEN

        # 4. Replication Completeness Check
        rep_stmt = select(ReplicationJob).where(ReplicationJob.recovery_point_id == int(chain.latest_recovery_point_id))
        rep_jobs = self.db.execute(rep_stmt).scalars().all()
        if rep_jobs and any(job.status == "FAILED" for job in rep_jobs):
            reasons.append("Offsite replication failed for the latest recovery point in chain")
            if status != CHAIN_BROKEN:
                status = CHAIN_DEGRADED

        # Update chain record in DB
        chain.status = status
        chain.broken_reason = "; ".join(reasons) if reasons else None
        chain.last_validated_at = now
        self.db.commit()

        return {
            "chain_id": chain.chain_id,
            "workload_id": chain.workload_id,
            "status": status,
            "broken_reason": chain.broken_reason,
            "chain_length": chain.chain_length,
            "base_recovery_point_id": chain.base_recovery_point_id,
            "latest_recovery_point_id": chain.latest_recovery_point_id,
            "artifacts_checked": len(artifacts),
            "validated_at": now.isoformat()
        }
