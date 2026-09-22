from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.backup_policy import BackupPolicy, BackupPolicyPath
from app.models.user import User
from app.schemas.policy import PolicyCreate, PolicyUpdate, PolicyResponse, PolicyPathSchema
from app.schemas.common import ApiResponse
from app.security.dependencies import require_role, get_optional_current_user
from app.services.audit_service import log_audit_event

router = APIRouter(prefix="/policies", tags=["Backup Policies"])

@router.get("", response_model=ApiResponse[List[PolicyResponse]])
def list_policies(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    policies = db.query(BackupPolicy).all()
    results = []
    for p in policies:
        paths = [PolicyPathSchema.model_validate(path) for path in p.paths]
        res = PolicyResponse(
            id=p.id,
            name=p.name,
            description=p.description,
            backup_type=p.backup_type,
            change_detection=p.change_detection,
            rpo_target_seconds=p.rpo_target_seconds,
            compression_enabled=p.compression_enabled,
            encryption_enabled=p.encryption_enabled,
            cpu_limit_percent=p.cpu_limit_percent,
            network_limit_mbps=p.network_limit_mbps,
            retention_days=p.retention_days,
            is_active=p.is_active,
            created_at=p.created_at,
            updated_at=p.updated_at,
            paths=paths
        )
        results.append(res)

    return ApiResponse(
        success=True,
        data=results,
        message=f"Retrieved {len(results)} policies"
    )

@router.get("/{policy_id}", response_model=ApiResponse[PolicyResponse])
def get_policy(
    policy_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    p = db.query(BackupPolicy).filter(BackupPolicy.id == policy_id).first()
    if not p:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy with ID {policy_id} not found"
        )

    paths = [PolicyPathSchema.model_validate(path) for path in p.paths]
    res = PolicyResponse(
        id=p.id,
        name=p.name,
        description=p.description,
        backup_type=p.backup_type,
        change_detection=p.change_detection,
        rpo_target_seconds=p.rpo_target_seconds,
        compression_enabled=p.compression_enabled,
        encryption_enabled=p.encryption_enabled,
        cpu_limit_percent=p.cpu_limit_percent,
        network_limit_mbps=p.network_limit_mbps,
        retention_days=p.retention_days,
        is_active=p.is_active,
        created_at=p.created_at,
        updated_at=p.updated_at,
        paths=paths
    )
    return ApiResponse(success=True, data=res, message="Policy retrieved successfully")

@router.post("", response_model=ApiResponse[PolicyResponse], status_code=status.HTTP_201_CREATED)
def create_policy(
    request: PolicyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "operator"]))
):
    existing = db.query(BackupPolicy).filter(BackupPolicy.name == request.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Policy with name '{request.name}' already exists"
        )

    policy = BackupPolicy(
        name=request.name,
        description=request.description,
        backup_type=request.backup_type,
        change_detection=request.change_detection,
        rpo_target_seconds=request.rpo_target_seconds,
        compression_enabled=request.compression_enabled,
        encryption_enabled=request.encryption_enabled,
        cpu_limit_percent=request.cpu_limit_percent,
        network_limit_mbps=request.network_limit_mbps,
        retention_days=request.retention_days,
        is_active=request.is_active
    )
    db.add(policy)
    db.flush()

    for p in request.paths:
        path_record = BackupPolicyPath(
            policy_id=policy.id,
            path_type=p.path_type,
            path_value=p.path_value,
            is_excluded=p.is_excluded
        )
        db.add(path_record)

    db.commit()
    db.refresh(policy)

    log_audit_event(
        db=db,
        action="POLICY_CREATED",
        resource_type="policy",
        resource_id=str(policy.id),
        user_id=current_user.id,
        details=f"Created backup policy '{policy.name}' with {len(request.paths)} paths"
    )

    paths = [PolicyPathSchema.model_validate(path) for path in policy.paths]
    res = PolicyResponse(
        id=policy.id,
        name=policy.name,
        description=policy.description,
        backup_type=policy.backup_type,
        change_detection=policy.change_detection,
        rpo_target_seconds=policy.rpo_target_seconds,
        compression_enabled=policy.compression_enabled,
        encryption_enabled=policy.encryption_enabled,
        cpu_limit_percent=policy.cpu_limit_percent,
        network_limit_mbps=policy.network_limit_mbps,
        retention_days=policy.retention_days,
        is_active=policy.is_active,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
        paths=paths
    )
    return ApiResponse(success=True, data=res, message="Policy created successfully")

@router.patch("/{policy_id}", response_model=ApiResponse[PolicyResponse])
def update_policy(
    policy_id: int,
    request: PolicyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "operator"]))
):
    p = db.query(BackupPolicy).filter(BackupPolicy.id == policy_id).first()
    if not p:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy with ID {policy_id} not found"
        )

    update_data = request.model_dump(exclude_unset=True, exclude={"paths"})
    for field, val in update_data.items():
        setattr(p, field, val)

    if request.paths is not None:
        db.query(BackupPolicyPath).filter(BackupPolicyPath.policy_id == p.id).delete()
        for path_item in request.paths:
            new_path = BackupPolicyPath(
                policy_id=p.id,
                path_type=path_item.path_type,
                path_value=path_item.path_value,
                is_excluded=path_item.is_excluded
            )
            db.add(new_path)

    db.commit()
    db.refresh(p)

    log_audit_event(
        db=db,
        action="POLICY_UPDATED",
        resource_type="policy",
        resource_id=str(p.id),
        user_id=current_user.id,
        details=f"Updated backup policy '{p.name}'"
    )

    paths = [PolicyPathSchema.model_validate(path) for path in p.paths]
    res = PolicyResponse(
        id=p.id,
        name=p.name,
        description=p.description,
        backup_type=p.backup_type,
        change_detection=p.change_detection,
        rpo_target_seconds=p.rpo_target_seconds,
        compression_enabled=p.compression_enabled,
        encryption_enabled=p.encryption_enabled,
        cpu_limit_percent=p.cpu_limit_percent,
        network_limit_mbps=p.network_limit_mbps,
        retention_days=p.retention_days,
        is_active=p.is_active,
        created_at=p.created_at,
        updated_at=p.updated_at,
        paths=paths
    )
    return ApiResponse(success=True, data=res, message="Policy updated successfully")

@router.delete("/{policy_id}", response_model=ApiResponse[dict])
def delete_policy(
    policy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    p = db.query(BackupPolicy).filter(BackupPolicy.id == policy_id).first()
    if not p:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy with ID {policy_id} not found"
        )
    name = p.name
    db.delete(p)
    db.commit()

    log_audit_event(
        db=db,
        action="POLICY_DELETED",
        resource_type="policy",
        resource_id=str(policy_id),
        user_id=current_user.id,
        details=f"Deleted backup policy '{name}'"
    )

    return ApiResponse(success=True, data={"id": policy_id}, message=f"Policy '{name}' deleted successfully")
