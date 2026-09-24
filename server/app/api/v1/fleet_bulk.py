"""REST API endpoints for RetroVault V9 Fleet-wide Bulk Operations."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.v9_schemas import BulkTriggerRequest, BulkOperationResponse
from app.services.fleet.bulk_service import BulkFleetService

router = APIRouter(prefix="/fleet/bulk", tags=["Fleet Bulk Operations"])


@router.post("/backup", response_model=BulkOperationResponse)
def trigger_bulk_backup(payload: BulkTriggerRequest, db: Session = Depends(get_db)):
    service = BulkFleetService(db)
    res = service.trigger_bulk_backup(
        client_ids=payload.client_ids,
        job_type=payload.job_type,
        priority=payload.priority,
        created_by=payload.created_by,
    )
    return BulkOperationResponse(
        operation_id=res["operation_id"],
        status=res["status"],
        target_count=res["target_count"],
        success_count=res["success_count"],
        failure_count=res["failure_count"],
        job_ids=res.get("job_ids", []),
    )


@router.get("/operations")
def list_bulk_operations(limit: int = 50, db: Session = Depends(get_db)):
    service = BulkFleetService(db)
    return service.list_operations(limit=limit)
