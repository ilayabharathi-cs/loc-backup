"""API Router for V8 Security Incidents (10-state lifecycle)."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.models.security_v8_models import SecurityIncident
from app.schemas.v8_schemas import (
    SecurityIncidentCreate,
    SecurityIncidentTransition,
    SecurityIncidentResponse,
)
from app.services.security.incident_manager import IncidentManager

router = APIRouter(prefix="/incidents", tags=["v8_incidents"])


@router.get("", response_model=List[SecurityIncidentResponse])
def list_incidents(
    status: Optional[str] = None,
    client_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(SecurityIncident)
    if status:
        query = query.filter(SecurityIncident.status == status.upper())
    if client_id:
        query = query.filter(SecurityIncident.client_id == client_id)
    return query.order_by(SecurityIncident.created_at.desc()).limit(limit).all()


@router.get("/{incident_id}", response_model=SecurityIncidentResponse)
def get_incident(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    inc = db.query(SecurityIncident).filter(SecurityIncident.id == incident_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    return inc


@router.post("", response_model=SecurityIncidentResponse)
def create_incident(
    incident_in: SecurityIncidentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    manager = IncidentManager(db)
    inc = manager.create_incident(
        title=incident_in.title,
        severity=incident_in.severity,
        client_id=incident_in.client_id,
        candidate_recovery_point_id=incident_in.candidate_recovery_point_id,
        containment_notes=incident_in.containment_notes
    )
    return inc


@router.post("/{incident_id}/transition")
def transition_incident(
    incident_id: int,
    transition_in: SecurityIncidentTransition,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    manager = IncidentManager(db)
    res = manager.transition_status(
        incident_id=incident_id,
        new_status=transition_in.status,
        operator_username=current_user.username,
        notes=transition_in.notes,
        candidate_rp_id=transition_in.candidate_rp_id
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "Transition failed"))
    return res
