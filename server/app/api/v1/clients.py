from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.database.session import get_db
from app.models.client import Client
from app.models.user import User
from app.schemas.client import ClientCreate, ClientUpdate, ClientResponse
from app.schemas.common import ApiResponse
from app.security.dependencies import get_current_user, require_role, get_optional_current_user
from app.services.audit_service import log_audit_event

router = APIRouter(prefix="/clients", tags=["Clients"])

def find_client(db: Session, client_identifier: str) -> Client:
    client = None
    if client_identifier.isdigit():
        client = db.query(Client).filter(Client.id == int(client_identifier)).first()
    if not client:
        client = db.query(Client).filter(Client.client_id == client_identifier).first()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client '{client_identifier}' not found"
        )
    return client

@router.get("", response_model=ApiResponse[List[ClientResponse]])
def list_clients(
    status: Optional[str] = Query(None, description="Filter by status (pending, active, offline, disabled)"),
    search: Optional[str] = Query(None, description="Search by hostname, client_id, or IP"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    query = db.query(Client)
    if status:
        query = query.filter(Client.status == status)
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Client.hostname.ilike(search_pattern),
                Client.client_id.ilike(search_pattern),
                Client.ip_address.ilike(search_pattern)
            )
        )
    clients = query.order_by(Client.client_id.asc()).all()
    return ApiResponse(
        success=True,
        data=[ClientResponse.model_validate(c) for c in clients],
        message=f"Retrieved {len(clients)} clients"
    )

@router.get("/{client_id}", response_model=ApiResponse[ClientResponse])
def get_client(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    client = find_client(db, client_id)
    return ApiResponse(
        success=True,
        data=ClientResponse.model_validate(client),
        message="Client retrieved successfully"
    )

@router.post("", response_model=ApiResponse[ClientResponse], status_code=status.HTTP_201_CREATED)
def create_client(
    request: ClientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "operator"]))
):
    existing = db.query(Client).filter(
        or_(Client.client_id == request.client_id, Client.device_id == request.device_id)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Client with this client_id or device_id already exists"
        )

    client = Client(
        client_id=request.client_id,
        hostname=request.hostname,
        device_id=request.device_id,
        os=request.os,
        os_version=request.os_version,
        ip_address=request.ip_address,
        agent_version=request.agent_version,
        status=request.status
    )
    db.add(client)
    db.commit()
    db.refresh(client)

    log_audit_event(
        db=db,
        action="CLIENT_CREATED",
        resource_type="client",
        resource_id=client.client_id,
        user_id=current_user.id,
        client_id=client.id,
        details=f"Created client {client.hostname} ({client.client_id})"
    )

    return ApiResponse(
        success=True,
        data=ClientResponse.model_validate(client),
        message="Client created successfully"
    )

@router.patch("/{client_id}", response_model=ApiResponse[ClientResponse])
def update_client(
    client_id: str,
    request: ClientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "operator"]))
):
    client = find_client(db, client_id)
    update_data = request.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(client, field, val)

    db.commit()
    db.refresh(client)

    log_audit_event(
        db=db,
        action="CLIENT_UPDATED",
        resource_type="client",
        resource_id=client.client_id,
        user_id=current_user.id,
        client_id=client.id,
        details=f"Updated client attributes: {list(update_data.keys())}"
    )

    return ApiResponse(
        success=True,
        data=ClientResponse.model_validate(client),
        message="Client updated successfully"
    )

@router.delete("/{client_id}", response_model=ApiResponse[dict])
def delete_client(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    client = find_client(db, client_id)
    cid = client.client_id
    db.delete(client)
    db.commit()

    log_audit_event(
        db=db,
        action="CLIENT_DELETED",
        resource_type="client",
        resource_id=cid,
        user_id=current_user.id,
        details=f"Deleted client {cid}"
    )

    return ApiResponse(
        success=True,
        data={"client_id": cid},
        message=f"Client {cid} deleted successfully"
    )

@router.post("/{client_id}/approve", response_model=ApiResponse[ClientResponse])
def approve_client(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "operator"]))
):
    client = find_client(db, client_id)
    client.status = "active"
    db.commit()
    db.refresh(client)

    log_audit_event(
        db=db,
        action="CLIENT_APPROVED",
        resource_type="client",
        resource_id=client.client_id,
        user_id=current_user.id,
        client_id=client.id,
        details=f"Approved client enrollment for {client.hostname}"
    )

    return ApiResponse(
        success=True,
        data=ClientResponse.model_validate(client),
        message="Client approved and status set to active"
    )

@router.post("/{client_id}/disable", response_model=ApiResponse[ClientResponse])
def disable_client(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "operator"]))
):
    client = find_client(db, client_id)
    client.status = "disabled"
    db.commit()
    db.refresh(client)

    log_audit_event(
        db=db,
        action="CLIENT_DISABLED",
        resource_type="client",
        resource_id=client.client_id,
        user_id=current_user.id,
        client_id=client.id,
        details=f"Disabled client {client.hostname}"
    )

    return ApiResponse(
        success=True,
        data=ClientResponse.model_validate(client),
        message="Client disabled successfully"
    )

@router.post("/{client_id}/backup", response_model=ApiResponse[dict])
def trigger_client_backup(
    client_id: str,
    policy_id: Optional[int] = Query(None),
    backup_type: Optional[str] = Query(None),
    request_data: Optional[dict] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """Trigger a backup job (full or incremental) for a specific client workstation."""
    import datetime
    from app.models.backup_job import BackupJob
    from app.models.backup_policy import BackupPolicy

    client = find_client(db, client_id)
    eff_policy_id = policy_id
    if not eff_policy_id and request_data:
        eff_policy_id = request_data.get("policy_id")
    if not eff_policy_id:
        active_policy = db.query(BackupPolicy).filter(BackupPolicy.is_active == True).first()
        eff_policy_id = active_policy.id if active_policy else None

    # Resolve backup_type
    raw_type = backup_type
    if not raw_type and request_data:
        raw_type = request_data.get("backup_type")
    eff_backup_type = (raw_type or "full").lower()

    # Check for existing active or pending job for this client
    existing_job = db.query(BackupJob).filter(
        BackupJob.client_id == client.id,
        BackupJob.status.in_(["pending", "queued", "running"])
    ).first()

    if existing_job:
        return ApiResponse(
            success=True,
            data={
                "job_id": existing_job.job_id,
                "client_id": client.client_id,
                "backup_type": getattr(existing_job, "backup_type", "full"),
                "status": existing_job.status,
                "already_active": True
            },
            message=f"Backup job {existing_job.job_id} is already active/queued for {client.client_id}"
        )

    job_count = db.query(BackupJob).count()
    new_job_id = f"JOB-{9400 + job_count + 1}"
    now = datetime.datetime.now(datetime.timezone.utc)

    job = BackupJob(
        job_id=new_job_id,
        client_id=client.id,
        policy_id=eff_policy_id,
        backup_type=eff_backup_type,
        status="pending",
        scheduled_at=now,
        created_at=now
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    log_audit_event(
        db=db,
        action="BACKUP_TRIGGERED",
        resource_type="client",
        resource_id=client.client_id,
        user_id=current_user.id if current_user else None,
        client_id=client.id,
        details=f"On-demand {eff_backup_type.upper()} backup job {job.job_id} scheduled for {client.hostname}"
    )

    return ApiResponse(
        success=True,
        data={
            "id": job.id,
            "job_id": job.job_id,
            "client_id": client.client_id,
            "policy_id": job.policy_id,
            "backup_type": job.backup_type,
            "status": job.status,
            "scheduled_at": now.isoformat()
        },
        message=f"{eff_backup_type.upper()} backup job {job.job_id} queued for {client.client_id}"
    )

