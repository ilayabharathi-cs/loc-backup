"""Backup Chains REST API router for RetroVault V11."""

import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database.session import get_db
from app.models.user import User
from app.models.workload_v11_models import BackupChain
from app.security.dependencies import get_current_user
from app.services.workload.backup_chain_validator import BackupChainValidator

router = APIRouter(prefix="/backup-chains", tags=["Backup Chains"])


def _serialize_chain(c: BackupChain) -> dict:
    return {
        "id": c.id,
        "chain_id": c.chain_id,
        "workload_id": c.workload_id,
        "base_recovery_point_id": c.base_recovery_point_id,
        "latest_recovery_point_id": c.latest_recovery_point_id,
        "chain_length": c.chain_length,
        "status": c.status,
        "broken_reason": c.broken_reason,
        "last_validated_at": c.last_validated_at.isoformat(),
        "metadata": json.loads(c.metadata_json or "{}")
    }


@router.get("/")
def list_backup_chains(
    workload_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List backup chains with optional filtering."""
    stmt = select(BackupChain)
    if workload_id:
        stmt = stmt.where(BackupChain.workload_id == workload_id)
    if status:
        stmt = stmt.where(BackupChain.status == status)
    chains = db.execute(stmt).scalars().all()
    return [_serialize_chain(c) for c in chains]


@router.post("/{chain_id}/validate")
def validate_backup_chain(
    chain_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Execute integrity validation on a backup chain."""
    validator = BackupChainValidator(db)
    result = validator.validate_chain(chain_id)
    if result.get("status") == "UNKNOWN" and "not found" in (result.get("broken_reason") or ""):
        raise HTTPException(status_code=404, detail=result.get("broken_reason"))
    return result
