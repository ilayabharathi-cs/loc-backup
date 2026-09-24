"""API Router for V8 Fleet Management, Groups, Policy Hierarchy & Drift Detection."""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.models.client import Client
from app.models.security_v8_models import ClientGroup, ConfigurationDrift
from app.schemas.v8_schemas import ClientGroupCreate, ClientGroupResponse
from app.services.fleet.policy_orchestrator import PolicyOrchestrator
from app.services.fleet.drift_detector import DriftDetector

router = APIRouter(prefix="/fleet", tags=["v8_fleet"])


# Groups
@router.get("/groups", response_model=List[ClientGroupResponse])
def list_client_groups(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(ClientGroup).all()


@router.post("/groups", response_model=ClientGroupResponse)
def create_client_group(
    group_in: ClientGroupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    group = ClientGroup(**group_in.model_dump())
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


@router.post("/clients/{client_id}/assign-group")
def assign_client_group(
    client_id: int,
    group_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    client.group_id = group_id
    db.commit()
    return {"message": "Client group updated", "client_id": client_id, "group_id": group_id}


# Policy Hierarchy & Dry-Run Simulation
@router.get("/clients/{client_id}/effective-policy")
def get_client_effective_policy(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    orchestrator = PolicyOrchestrator(db)
    res = orchestrator.resolve_effective_policy(client_id)
    if "error" in res:
        raise HTTPException(status_code=404, detail=res["error"])
    return res


@router.post("/clients/{client_id}/simulate-policy/{policy_id}")
def simulate_policy_dry_run(
    client_id: int,
    policy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    orchestrator = PolicyOrchestrator(db)
    res = orchestrator.simulate_policy_dry_run(client_id, policy_id)
    if "error" in res:
        raise HTTPException(status_code=404, detail=res["error"])
    return res


# Drift Detection
@router.get("/drifts")
def list_configuration_drifts(
    client_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(ConfigurationDrift)
    if client_id:
        query = query.filter(ConfigurationDrift.client_id == client_id)
    if status:
        query = query.filter(ConfigurationDrift.status == status.upper())
    return query.order_by(ConfigurationDrift.detected_at.desc()).all()


@router.post("/clients/{client_id}/detect-drift")
def trigger_client_drift_detection(
    client_id: int,
    agent_config: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    detector = DriftDetector(db)
    drifts = detector.detect_drift(client_id, agent_config)
    return {
        "client_id": client_id,
        "drifts_detected": len(drifts),
        "drifts": [{"type": d.drift_type, "expected": d.expected_value, "actual": d.actual_value, "severity": d.severity} for d in drifts]
    }
