"""API Router for V8 Safe Ransomware & DR Sandbox Simulations."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.models.security_v8_models import SecuritySimulation
from app.schemas.v8_schemas import SimulationTrigger, SimulationResponse
from app.services.security.simulation_engine import SimulationEngine

router = APIRouter(prefix="/simulations", tags=["v8_simulations"])


@router.get("", response_model=List[SimulationResponse])
def list_simulations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(SecuritySimulation).order_by(SecuritySimulation.started_at.desc()).all()


@router.post("/run")
def trigger_simulation(
    sim_in: SimulationTrigger,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    engine = SimulationEngine(db)
    result = engine.run_simulation(
        scenario_type=sim_in.scenario_type,
        file_count=sim_in.file_count,
        encryption_ratio=sim_in.encryption_ratio
    )
    return result
