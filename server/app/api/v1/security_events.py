"""API Router for V8 Security Events, Anomaly Detection & Recovery Point Protection."""

import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.models.recovery_point import RecoveryPoint
from app.models.security_v8_models import SecurityEvent, SecurityProfile
from app.schemas.v8_schemas import (
    SecurityEventResponse,
    SecurityProfileCreate,
    SecurityProfileResponse,
    RecoveryPointProtectionUpdate,
)
from app.services.security.anomaly_detector import AnomalyDetector
from app.services.security.clean_recovery_selector import CleanRecoverySelector

router = APIRouter(prefix="/security", tags=["v8_security"])


@router.get("/events", response_model=List[SecurityEventResponse])
def list_security_events(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    client_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(SecurityEvent)
    if status:
        query = query.filter(SecurityEvent.status == status.upper())
    if severity:
        query = query.filter(SecurityEvent.severity == severity.upper())
    if client_id:
        query = query.filter(SecurityEvent.client_id == client_id)

    return query.order_by(SecurityEvent.created_at.desc()).limit(limit).all()


@router.post("/events/{event_id}/acknowledge")
def acknowledge_security_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    event = db.query(SecurityEvent).filter(SecurityEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Security event not found")

    event.status = "ACKNOWLEDGED"
    event.acknowledged_at = datetime.datetime.now(datetime.timezone.utc)
    db.commit()
    return {"message": "Security event acknowledged", "event_id": event_id}


@router.post("/events/{event_id}/resolve")
def resolve_security_event(
    event_id: int,
    status_choice: str = "RESOLVED",  # RESOLVED or FALSE_POSITIVE
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    event = db.query(SecurityEvent).filter(SecurityEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Security event not found")

    event.status = status_choice.upper()
    event.resolved_at = datetime.datetime.now(datetime.timezone.utc)
    event.resolved_by = current_user.username
    db.commit()
    return {"message": f"Security event marked as {event.status}", "event_id": event_id}


@router.post("/runs/{run_id}/evaluate-anomalies")
def evaluate_run_anomalies(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    detector = AnomalyDetector(db)
    result = detector.evaluate_backup_run(run_id)
    return result


@router.get("/clean-recovery/{client_id}")
def discover_clean_recovery_points(
    client_id: int,
    before: Optional[datetime.datetime] = None,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    selector = CleanRecoverySelector(db)
    points = selector.discover_clean_points(client_id, incident_timestamp=before, limit=limit)
    return {"client_id": client_id, "clean_candidates": points}


# Security Profiles
@router.get("/profiles", response_model=List[SecurityProfileResponse])
def list_security_profiles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(SecurityProfile).all()


@router.post("/profiles", response_model=SecurityProfileResponse)
def create_security_profile(
    profile_in: SecurityProfileCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = SecurityProfile(**profile_in.model_dump())
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


# Recovery Point Protection
@router.post("/recovery-points/{rp_id}/protect")
def set_recovery_point_protection(
    rp_id: int,
    protect_in: RecoveryPointProtectionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rp = db.query(RecoveryPoint).filter(RecoveryPoint.id == rp_id).first()
    if not rp:
        raise HTTPException(status_code=404, detail="Recovery point not found")

    rp.protection_state = protect_in.protection_state.upper()
    rp.protected_reason = protect_in.reason
    rp.protected_by = current_user.username
    rp.protection_created_at = datetime.datetime.now(datetime.timezone.utc)
    if protect_in.hold_days:
        rp.security_hold_until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=protect_in.hold_days)
    else:
        rp.security_hold_until = None

    db.commit()
    return {
        "recovery_point_id": rp.id,
        "protection_state": rp.protection_state,
        "security_hold_until": rp.security_hold_until.isoformat() if rp.security_hold_until else None,
        "protected_by": rp.protected_by
    }


@router.post("/recovery-points/{rp_id}/release-protection")
def release_recovery_point_protection(
    rp_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rp = db.query(RecoveryPoint).filter(RecoveryPoint.id == rp_id).first()
    if not rp:
        raise HTTPException(status_code=404, detail="Recovery point not found")

    rp.protection_state = "NORMAL"
    rp.security_hold_until = None
    rp.protected_reason = "Protection released by admin"
    rp.protected_by = current_user.username
    db.commit()
    return {"message": "Protection released", "recovery_point_id": rp.id}
