"""RetroVault V11: Workload Consistency Classification and Verification Service."""

import json
import uuid
import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.workload_v11_models import ApplicationConsistencyRecord
from app.services.workload.provider import (
    FILE_SYSTEM_CONSISTENT,
    APPLICATION_CONSISTENT,
    CRASH_CONSISTENT,
    PARTIAL,
    UNKNOWN,
    FAILED,
    ConsistencyResult
)


class WorkloadConsistencyService:
    """Verifies and classifies factual application consistency for Recovery Points."""

    def __init__(self, db: Session):
        self.db = db

    def evaluate_and_record_consistency(
        self,
        recovery_point_id: str,
        workload_id: str,
        consistency_result: ConsistencyResult,
        verified_by: str = "SYSTEM"
    ) -> ApplicationConsistencyRecord:
        """Validate evidence and record an immutable ApplicationConsistencyRecord."""
        # Enforce rule: Never claim APPLICATION_CONSISTENT without factual verification
        state = consistency_result.consistency_state
        if state == APPLICATION_CONSISTENT and not consistency_result.verified:
            # Downgrade to CRASH_CONSISTENT if verification failed or was missing
            state = CRASH_CONSISTENT

        evidence = dict(consistency_result.evidence)
        if consistency_result.notes:
            evidence["notes"] = consistency_result.notes

        record_id = f"acr-{uuid.uuid4().hex[:12]}"
        now = datetime.datetime.now(datetime.timezone.utc)

        record = ApplicationConsistencyRecord(
            record_id=record_id,
            recovery_point_id=recovery_point_id,
            workload_id=workload_id,
            consistency_state=state,
            verification_method=consistency_result.verification_method,
            evidence_json=json.dumps(evidence),
            verified_at=now,
            verified_by=verified_by
        )

        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_consistency_record(self, recovery_point_id: str) -> Optional[ApplicationConsistencyRecord]:
        stmt = select(ApplicationConsistencyRecord).where(
            ApplicationConsistencyRecord.recovery_point_id == recovery_point_id
        )
        return self.db.execute(stmt).scalars().first()
