"""Security API router for RetroVault V7."""

import json
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.user import User
from app.models.security_models import MfaSetting, AgentCredential
from app.models.audit_log import AuditLog
from app.schemas.common import ApiResponse
from app.schemas.v7_schemas import MfaSetupResponse, MfaVerifyRequest
from app.security.dependencies import get_current_user, require_role, require_permission, ROLE_PERMISSIONS
from app.security.mfa import TotpManager
from app.security.secret_manager import get_secret_manager
from app.services.audit_service import log_audit_event

router = APIRouter(prefix="/security", tags=["Security & Compliance"])


@router.get("/overview", response_model=ApiResponse[Dict[str, Any]])
def get_security_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve security posture overview: MFA status, active credentials, audit event counts."""
    mfa = db.query(MfaSetting).filter(MfaSetting.user_id == current_user.id).first()
    active_creds = db.query(AgentCredential).filter(AgentCredential.status == "ACTIVE").count()
    total_audits = db.query(AuditLog).count()

    return ApiResponse(
        success=True,
        data={
            "user_id": current_user.id,
            "username": current_user.username,
            "role": current_user.role,
            "mfa_enabled": bool(mfa and mfa.is_enabled),
            "active_agent_credentials": active_creds,
            "total_audit_events": total_audits,
            "permissions": ROLE_PERMISSIONS.get(current_user.role, [])
        },
        message="Security overview retrieved"
    )


@router.post("/mfa/setup", response_model=ApiResponse[MfaSetupResponse])
def setup_mfa(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Initialize TOTP-based Multi-Factor Authentication enrollment."""
    sec_mgr = get_secret_manager()
    secret = TotpManager.generate_secret()
    uri = TotpManager.generate_provisioning_uri(current_user.username, secret)
    recovery_codes = TotpManager.generate_recovery_codes(8)
    hashed_codes = [TotpManager.hash_recovery_code(c) for c in recovery_codes]

    # Save or update MfaSetting in pending/disabled state
    mfa = db.query(MfaSetting).filter(MfaSetting.user_id == current_user.id).first()
    if not mfa:
        mfa = MfaSetting(
            user_id=current_user.id,
            secret_encrypted=sec_mgr.encrypt_secret(secret),
            recovery_codes_hash=json.dumps(hashed_codes),
            is_enabled=False
        )
        db.add(mfa)
    else:
        mfa.secret_encrypted = sec_mgr.encrypt_secret(secret)
        mfa.recovery_codes_hash = json.dumps(hashed_codes)
        mfa.is_enabled = False

    db.commit()

    log_audit_event(
        db=db,
        action="MFA_SETUP_INITIATED",
        resource_type="security",
        resource_id=str(current_user.id),
        user_id=current_user.id,
        details=f"User {current_user.username} initiated MFA enrollment"
    )

    return ApiResponse(
        success=True,
        data=MfaSetupResponse(
            secret=secret,
            provisioning_uri=uri,
            recovery_codes=recovery_codes
        ),
        message="MFA enrollment initiated. Verify with 6-digit code to activate."
    )


@router.post("/mfa/verify", response_model=ApiResponse[dict])
def verify_mfa(
    request: MfaVerifyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Verify TOTP code to confirm and activate MFA."""
    mfa = db.query(MfaSetting).filter(MfaSetting.user_id == current_user.id).first()
    if not mfa:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MFA setup has not been initiated")

    sec_mgr = get_secret_manager()
    secret = sec_mgr.decrypt_secret(mfa.secret_encrypted)

    is_valid = TotpManager.verify_code(secret, request.code)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid TOTP authentication code")

    mfa.is_enabled = True
    db.commit()

    log_audit_event(
        db=db,
        action="MFA_ENABLED",
        resource_type="security",
        resource_id=str(current_user.id),
        user_id=current_user.id,
        details=f"User {current_user.username} enabled MFA"
    )

    return ApiResponse(success=True, data={"mfa_enabled": True}, message="MFA successfully activated")


@router.post("/mfa/disable", response_model=ApiResponse[dict])
def disable_mfa(
    request: MfaVerifyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Disable MFA using a valid TOTP code or recovery code."""
    mfa = db.query(MfaSetting).filter(MfaSetting.user_id == current_user.id).first()
    if not mfa or not mfa.is_enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MFA is not enabled")

    sec_mgr = get_secret_manager()
    secret = sec_mgr.decrypt_secret(mfa.secret_encrypted)

    is_valid = TotpManager.verify_code(secret, request.code)
    if not is_valid:
        # Check recovery codes
        hashed = json.loads(mfa.recovery_codes_hash)
        matched, _ = TotpManager.verify_and_consume_recovery_code(request.code, hashed)
        if not matched:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid TOTP or recovery code")

    mfa.is_enabled = False
    db.commit()

    log_audit_event(
        db=db,
        action="MFA_DISABLED",
        resource_type="security",
        resource_id=str(current_user.id),
        user_id=current_user.id,
        details=f"User {current_user.username} disabled MFA"
    )

    return ApiResponse(success=True, data={"mfa_enabled": False}, message="MFA successfully disabled")


@router.get("/audit", response_model=ApiResponse[List[Dict[str, Any]]])
def get_security_audit_events(
    limit: int = Query(50, ge=1, le=500),
    action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("audit.read"))
):
    """Retrieve filtered security and administrative audit trail events."""
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action)
    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)

    logs = query.order_by(AuditLog.created_at.desc()).limit(limit).all()
    data = [
        {
            "id": l.id,
            "action": l.action,
            "resource_type": l.resource_type,
            "resource_id": l.resource_id,
            "user_id": l.user_id,
            "details": l.details,
            "timestamp": l.created_at.isoformat() if l.created_at else None
        }
        for l in logs
    ]
    return ApiResponse(success=True, data=data, message=f"Retrieved {len(data)} audit log events")


@router.get("/permissions", response_model=ApiResponse[Dict[str, List[str]]])
def get_permissions_matrix():
    """Retrieve full role-based permissions matrix."""
    return ApiResponse(
        success=True,
        data=ROLE_PERMISSIONS,
        message="Role permissions matrix retrieved"
    )
