"""Dependency Graph REST API router for RetroVault V11."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database.session import get_db
from app.models.user import User
from app.models.workload_v11_models import DependencyRelation
from app.security.dependencies import get_current_user
from app.schemas.v11_schemas import DependencyCheckRequest, DependencyCheckResponse
from app.services.workload.dependency_graph import DependencyGraphEngine

router = APIRouter(prefix="/dependencies", tags=["Dependency Graph"])


@router.get("/")
def list_dependencies(
    parent_type: Optional[str] = Query(None),
    parent_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Query dependencies in the graph."""
    stmt = select(DependencyRelation)
    if parent_type:
        stmt = stmt.where(DependencyRelation.parent_type == parent_type)
    if parent_id:
        stmt = stmt.where(DependencyRelation.parent_id == str(parent_id))
    deps = db.execute(stmt).scalars().all()
    return [
        {
            "id": d.id,
            "parent_type": d.parent_type,
            "parent_id": d.parent_id,
            "child_type": d.child_type,
            "child_id": d.child_id,
            "relation_type": d.relation_type,
            "created_at": d.created_at.isoformat()
        }
        for d in deps
    ]


@router.post("/check-safe-delete")
def check_safe_delete(
    req: DependencyCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Check if a resource can be safely deleted or garbage collected."""
    engine = DependencyGraphEngine(db)
    return engine.verify_safe_to_delete(req.resource_type, req.resource_id)
