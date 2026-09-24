"""Disaster Recovery & Readiness API router for RetroVault V7."""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.security_models import DrTest
from app.models.recovery_point import RecoveryPoint
from app.models.replication import ReplicationJob
from app.schemas.common import ApiResponse
from app.schemas.v7_schemas import DrTestRequest, DrTestResponse
from app.security.dependencies import require_role
from app.services.dr.dr_tester import DrTester
from app.services.observability.health_score import BackupHealthEvaluator
from app.services.observability.sla_monitor import SlaMonitor
from app.services.audit_service import log_audit_event

router = APIRouter(prefix="/dr", tags=["Disaster Recovery Readiness"])


@router.post("/tests", response_model=ApiResponse[DrTestResponse], status_code=status.HTTP_201_CREATED)
def run_automated_dr_test(
    request: DrTestRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["admin", "operator"]))
):
    """
    Execute an automated non-destructive disaster recovery verification drill.
    Restores to an isolated temporary sandbox, validates checksums and manifest consistency,
    cleans up sandbox directory, and records drill telemetry.
    """
    tester = DrTester(db)
    try:
        drill_result = tester.run_dr_drill(request.recovery_point_id)

        log_audit_event(
            db=db,
            action="DR_TEST_EXECUTED",
            resource_type="dr_test",
            resource_id=drill_result["test_id"],
            user_id=current_user.id if current_user else None,
            details=f"Executed automated DR drill {drill_result['test_id']}: Result={drill_result['result']}"
        )

        return ApiResponse(
            success=True,
            data=DrTestResponse(**drill_result),
            message=f"Disaster recovery test completed: {drill_result['result']}"
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"DR test failed: {e}")


@router.get("/tests", response_model=ApiResponse[List[DrTestResponse]])
def list_dr_tests(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Retrieve history of automated disaster recovery drill runs."""
    tests = db.query(DrTest).order_by(DrTest.started_at.desc()).limit(limit).all()
    data = [
        DrTestResponse(
            test_id=t.test_id,
            recovery_point_id=t.recovery_point_id,
            result=t.result,
            files_tested=t.files_tested,
            bytes_tested=t.bytes_tested,
            files_verified=t.files_verified,
            failures=t.failures,
            duration_seconds=t.duration_seconds,
            error_message=t.error_message,
            started_at=t.started_at.isoformat(),
            completed_at=t.completed_at.isoformat() if t.completed_at else None
        )
        for t in tests
    ]
    return ApiResponse(success=True, data=data, message=f"Retrieved {len(data)} DR test records")


@router.get("/readiness", response_model=ApiResponse[Dict[str, Any]])
def get_dr_readiness(db: Session = Depends(get_db)):
    """
    Retrieve comprehensive Disaster Recovery Readiness assessment:
    - Latest valid recovery point
    - Latest replicated recovery point
    - Last successful restore drill
    - Observed RPO compliance
    - Multi-indicator factual health indicators
    """
    latest_rp = db.query(RecoveryPoint).filter(
        RecoveryPoint.status.in_(["valid", "completed"])
    ).order_by(RecoveryPoint.created_at.desc()).first()

    latest_repl = db.query(ReplicationJob).filter(
        ReplicationJob.status == "COMPLETED"
    ).order_by(ReplicationJob.completed_at.desc()).first()

    latest_drill = db.query(DrTest).order_by(DrTest.started_at.desc()).first()

    health_eval = BackupHealthEvaluator(db)
    indicators = health_eval.evaluate_health_indicators()

    sla_mon = SlaMonitor(db)
    rpo_eval = sla_mon.evaluate_rpo_compliance()

    is_ready = (
        latest_rp is not None and
        (latest_drill is not None and latest_drill.result == "PASSED") and
        indicators.get("integrity_health", {}).get("state") != "ERROR" and
        indicators.get("repository_health", {}).get("state") != "ERROR"
    )

    reasons = []
    if not latest_rp:
        reasons.append("No valid recovery points available")
    if not latest_drill:
        reasons.append("No disaster recovery drill has been performed yet")
    elif latest_drill.result != "PASSED":
        reasons.append(f"Most recent DR drill failed: {latest_drill.error_message or 'Integrity mismatch'}")
    if indicators.get("integrity_health", {}).get("state") == "ERROR":
        reasons.append("Corrupted CAS storage objects detected in repository")

    return ApiResponse(
        success=True,
        data={
            "status": "RESTORE READY" if is_ready else "RESTORE READINESS DEGRADED",
            "is_ready": is_ready,
            "reasons": reasons,
            "latest_recovery_point": {
                "id": latest_rp.id if latest_rp else None,
                "timestamp": latest_rp.created_at.isoformat() if (latest_rp and latest_rp.created_at) else None,
                "backup_type": latest_rp.backup_type if latest_rp else None
            },
            "latest_replication": {
                "job_id": latest_repl.job_id if latest_repl else None,
                "completed_at": latest_repl.completed_at.isoformat() if (latest_repl and latest_repl.completed_at) else None
            },
            "latest_dr_drill": {
                "test_id": latest_drill.test_id if latest_drill else None,
                "result": latest_drill.result if latest_drill else None,
                "duration_seconds": latest_drill.duration_seconds if latest_drill else None,
                "timestamp": latest_drill.started_at.isoformat() if latest_drill else None
            },
            "rpo": rpo_eval,
            "health_indicators": indicators
        },
        message="Disaster recovery readiness assessment retrieved"
    )
