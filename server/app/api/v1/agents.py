import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.client import Client
from app.models.backup_policy import BackupPolicy
from app.schemas.client import AgentRegisterRequest, AgentHeartbeatRequest, AgentConfigResponse, ClientResponse
from app.schemas.common import ApiResponse
from app.services.audit_service import log_audit_event

router = APIRouter(prefix="/agents", tags=["Agent Foundation"])

@router.post("/register", response_model=ApiResponse[ClientResponse])
def register_agent(request: AgentRegisterRequest, db: Session = Depends(get_db)):
    # Check if client device already exists
    client = db.query(Client).filter(Client.device_id == request.device_id).first()
    if client:
        # Update existing client information
        client.hostname = request.hostname
        client.ip_address = request.ip_address
        client.agent_version = request.agent_version
        client.os = request.os
        client.os_version = request.os_version
        client.last_seen = datetime.datetime.now(datetime.timezone.utc)
        if client.status == "offline":
            client.status = "active"
        db.commit()
        db.refresh(client)
        msg = "Agent registration renewed"
    else:
        # Generate new client_id
        count = db.query(Client).count()
        new_client_id = f"PC-{count + 1:03d}"
        # Ensure client_id uniqueness
        while db.query(Client).filter(Client.client_id == new_client_id).first():
            count += 1
            new_client_id = f"PC-{count + 1:03d}"

        client = Client(
            client_id=new_client_id,
            device_id=request.device_id,
            hostname=request.hostname,
            os=request.os,
            os_version=request.os_version,
            ip_address=request.ip_address,
            agent_version=request.agent_version,
            status="pending",
            last_seen=datetime.datetime.now(datetime.timezone.utc)
        )
        db.add(client)
        db.commit()
        db.refresh(client)
        msg = "New agent registered (status: pending approval)"

    log_audit_event(
        db=db,
        action="AGENT_REGISTERED",
        resource_type="agent",
        resource_id=client.client_id,
        client_id=client.id,
        details=f"Agent from {client.hostname} ({client.ip_address}) registered"
    )

    return ApiResponse(
        success=True,
        data=ClientResponse.model_validate(client),
        message=msg
    )

@router.post("/heartbeat", response_model=ApiResponse[dict])
def agent_heartbeat(request: AgentHeartbeatRequest, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.device_id == request.device_id).first()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent device not registered"
        )

    now = datetime.datetime.now(datetime.timezone.utc)
    client.last_seen = now
    if request.ip_address:
        client.ip_address = request.ip_address
    if request.agent_version:
        client.agent_version = request.agent_version
    if client.status != "disabled" and request.status:
        client.status = request.status

    db.commit()

    return ApiResponse(
        success=True,
        data={
            "client_id": client.client_id,
            "status": client.status,
            "acknowledged_at": now.isoformat()
        },
        message="Heartbeat acknowledged"
    )

@router.get("/{client_id}/config", response_model=ApiResponse[AgentConfigResponse])
def get_agent_config(client_id: str, db: Session = Depends(get_db)):
    client = None
    if client_id.isdigit():
        client = db.query(Client).filter(Client.id == int(client_id)).first()
    if not client:
        client = db.query(Client).filter(Client.client_id == client_id).first()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )

    # Find active default policy
    policy = db.query(BackupPolicy).filter(BackupPolicy.is_active == True).first()
    policy_dict = None
    if policy:
        paths = [
            {"path_type": p.path_type, "path_value": p.path_value, "is_excluded": p.is_excluded}
            for p in policy.paths
        ]
        policy_dict = {
            "id": policy.id,
            "name": policy.name,
            "backup_type": policy.backup_type,
            "change_detection": policy.change_detection,
            "rpo_target_seconds": policy.rpo_target_seconds,
            "compression_enabled": policy.compression_enabled,
            "encryption_enabled": policy.encryption_enabled,
            "cpu_limit_percent": policy.cpu_limit_percent,
            "network_limit_mbps": policy.network_limit_mbps,
            "paths": paths
        }

    # Check for pending backup job for this client
    from app.models.backup_job import BackupJob
    pending_job = db.query(BackupJob).filter(
        BackupJob.client_id == client.id,
        BackupJob.status.in_(["pending", "queued"])
    ).order_by(BackupJob.created_at.asc()).first()

    pending_job_dict = None
    if pending_job:
        pending_job_dict = {
            "id": pending_job.id,
            "job_id": pending_job.job_id,
            "policy_id": pending_job.policy_id,
            "backup_type": getattr(pending_job, "backup_type", "full") or "full",
            "status": pending_job.status
        }

    config = AgentConfigResponse(
        client_id=client.client_id,
        device_id=client.device_id,
        status=client.status,
        server_time=datetime.datetime.now(datetime.timezone.utc),
        heartbeat_interval_seconds=15,
        policy=policy_dict,
        pending_job=pending_job_dict
    )

    return ApiResponse(
        success=True,
        data=config,
        message="Agent configuration retrieved"
    )


@router.post("/{client_id}/rotate-credentials", response_model=ApiResponse[dict])
def rotate_agent_credentials(client_id: str, db: Session = Depends(get_db)):
    """Issue a new credential token for an agent. Status remains PENDING_CONFIRMATION until confirmed."""
    import secrets
    import hashlib
    from app.models.security_models import AgentCredential

    client = None
    if client_id.isdigit():
        client = db.query(Client).filter(Client.id == int(client_id)).first()
    if not client:
        client = db.query(Client).filter(Client.client_id == client_id).first()
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

    new_token = f"rv_token_{secrets.token_urlsafe(32)}"
    token_hash = hashlib.sha256(new_token.encode("utf-8")).hexdigest()
    now = datetime.datetime.now(datetime.timezone.utc)

    cred = AgentCredential(
        client_id=client.id,
        token_hash=token_hash,
        status="PENDING_CONFIRMATION",
        issued_at=now,
        expires_at=now + datetime.timedelta(days=90),
        rotation_reason="Administrator or Agent initiated credential rotation"
    )
    db.add(cred)
    db.commit()
    db.refresh(cred)

    log_audit_event(
        db=db,
        action="AGENT_CREDENTIAL_ROTATED",
        resource_type="agent",
        resource_id=client.client_id,
        client_id=client.id,
        details=f"Issued new credential token for client {client.client_id}"
    )

    return ApiResponse(
        success=True,
        data={
            "client_id": client.client_id,
            "device_id": client.device_id,
            "new_token": new_token,
            "credential_id": cred.id,
            "status": cred.status,
            "expires_at": cred.expires_at.isoformat() if cred.expires_at else None
        },
        message="New agent credential token issued. Agent must confirm receipt to finalize rotation."
    )


@router.post("/{client_id}/confirm-credentials", response_model=ApiResponse[dict])
def confirm_agent_credentials(client_id: str, credential_id: Optional[int] = None, db: Session = Depends(get_db)):
    """Confirm new credential token and revoke old credentials."""
    from app.models.security_models import AgentCredential

    client = None
    if client_id.isdigit():
        client = db.query(Client).filter(Client.id == int(client_id)).first()
    if not client:
        client = db.query(Client).filter(Client.client_id == client_id).first()
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

    now = datetime.datetime.now(datetime.timezone.utc)

    # Find the pending credential
    query = db.query(AgentCredential).filter(AgentCredential.client_id == client.id)
    if credential_id:
        target_cred = query.filter(AgentCredential.id == credential_id).first()
    else:
        target_cred = query.filter(AgentCredential.status == "PENDING_CONFIRMATION").order_by(AgentCredential.issued_at.desc()).first()

    if not target_cred:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No pending credentials found for this client")

    # Invalidate old credentials
    old_creds = db.query(AgentCredential).filter(
        AgentCredential.client_id == client.id,
        AgentCredential.id != target_cred.id,
        AgentCredential.status == "ACTIVE"
    ).all()
    for c in old_creds:
        c.status = "REVOKED"
        c.revoked_at = now

    # Activate new credential
    target_cred.status = "ACTIVE"
    target_cred.confirmed_at = now
    db.commit()

    log_audit_event(
        db=db,
        action="AGENT_CREDENTIAL_CONFIRMED",
        resource_type="agent",
        resource_id=client.client_id,
        client_id=client.id,
        details=f"Agent {client.client_id} confirmed new credential token #{target_cred.id}. Revoked {len(old_creds)} old credentials."
    )

    return ApiResponse(
        success=True,
        data={
            "client_id": client.client_id,
            "credential_id": target_cred.id,
            "status": "ACTIVE",
            "revoked_count": len(old_creds)
        },
        message="Agent credential rotation confirmed and activated"
    )

