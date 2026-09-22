import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.database.session import get_db
from app.models.audit_log import AuditLog
from app.models.client import Client
from app.schemas.activity import AuditLogResponse
from app.schemas.common import ApiResponse
from app.security.dependencies import get_optional_current_user

router = APIRouter(prefix="/activity", tags=["Audit & Activity Logs"])

@router.get("", response_model=ApiResponse[List[AuditLogResponse]])
def list_activity(
    client: Optional[str] = Query(None, description="Filter by client_id or client identifier"),
    severity: Optional[str] = Query(None, description="Filter by severity (INFO, WARNING, ERROR)"),
    action: Optional[str] = Query(None, description="Filter by action keyword"),
    date_from: Optional[datetime.datetime] = Query(None, description="Start date filter"),
    date_to: Optional[datetime.datetime] = Query(None, description="End date filter"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user=Depends(get_optional_current_user)
):
    query = db.query(AuditLog)

    if client:
        if client.isdigit():
            query = query.filter(AuditLog.client_id == int(client))
        else:
            c = db.query(Client).filter(Client.client_id == client).first()
            if c:
                query = query.filter(AuditLog.client_id == c.id)

    if action:
        query = query.filter(AuditLog.action.ilike(f"%{action}%"))

    if date_from:
        query = query.filter(AuditLog.created_at >= date_from)

    if date_to:
        query = query.filter(AuditLog.created_at <= date_to)

    logs = query.order_by(AuditLog.created_at.desc()).limit(limit).all()

    results = []
    for l in logs:
        # Determine severity
        sev = "INFO"
        if "FAILED" in l.action or "ERROR" in l.action or "TIMEOUT" in (l.details or ""):
            sev = "ERROR"
        elif "WARNING" in l.action or "BREACH" in l.action or "DISABLE" in l.action:
            sev = "WARNING"

        if severity and severity.upper() != "ALL" and sev != severity.upper():
            continue

        results.append(AuditLogResponse(
            id=l.id,
            user_id=l.user_id,
            username=l.user.username if l.user else "SYSTEM",
            client_id=l.client_id,
            client_identifier=l.client.client_id if l.client else None,
            action=l.action,
            resource_type=l.resource_type,
            resource_id=l.resource_id,
            ip_address=l.ip_address,
            details=l.details,
            created_at=l.created_at,
            severity=sev
        ))

    return ApiResponse(success=True, data=results, message=f"Retrieved {len(results)} activity records")
