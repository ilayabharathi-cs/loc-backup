from typing import Optional
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog

def log_audit_event(
    db: Session,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    user_id: Optional[int] = None,
    client_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    details: Optional[str] = None
) -> AuditLog:
    entry = AuditLog(
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        user_id=user_id,
        client_id=client_id,
        ip_address=ip_address,
        details=details
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
