"""Storage Tiers & Cloud Credentials API endpoints for RetroVault V12."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.v12_schemas import (
    CloudCredentialCreate,
    CloudCredentialResponse,
    StorageTierCreate,
    StorageTierUpdate,
    StorageTierResponse,
    StorageTierValidateResponse,
    OffloadRequest,
    OffloadResponse,
    OffloadItemResponse,
    RemoteVerificationResponse
)
from app.security.dependencies import require_role, get_optional_current_user, get_current_user
from app.services.v12.cloud.credential_store import CredentialStoreService
from app.services.v12.cloud.tiering_manager import TieringManager

cloud_credentials_router = APIRouter(prefix="/cloud/credentials", tags=["Cloud Credentials"])
storage_tiers_router = APIRouter(prefix="/storage/tiers", tags=["Storage Tiers"])


# ==============================================================================
# Cloud Credentials Endpoints
# ==============================================================================

@cloud_credentials_router.post(
    "",
    response_model=ApiResponse[CloudCredentialResponse],
    status_code=status.HTTP_201_CREATED
)
def create_credential(
    payload: CloudCredentialCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "operator"]))
):
    """
    Register and securely store cloud storage credentials.
    Access keys and secret keys are encrypted at rest.
    The secret key is never returned or logged.
    """
    svc = CredentialStoreService(db)
    try:
        cred = svc.create_credential(
            name=payload.name,
            provider=payload.provider,
            access_key=payload.access_key,
            secret_key=payload.secret_key,
            endpoint=payload.endpoint,
            region=payload.region,
            prefix=payload.prefix,
            use_tls=payload.use_tls,
            verify_ssl=payload.verify_ssl,
            user_id=current_user.id if current_user else None
        )
        safe_data = svc.get_credential_safe(cred.id)
        return ApiResponse(
            success=True,
            data=CloudCredentialResponse(**safe_data),
            message=f"Cloud credential '{cred.name}' registered securely"
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to store cloud credential")


@cloud_credentials_router.get(
    "",
    response_model=ApiResponse[List[CloudCredentialResponse]]
)
def list_credentials(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    List configured cloud credentials.
    Access keys are masked; secret keys are NEVER included.
    """
    svc = CredentialStoreService(db)
    creds = svc.list_credentials_safe()
    return ApiResponse(
        success=True,
        data=[CloudCredentialResponse(**c) for c in creds],
        message=f"Retrieved {len(creds)} cloud credentials"
    )


@cloud_credentials_router.delete(
    "/{credential_id}",
    response_model=ApiResponse[dict]
)
def delete_credential(
    credential_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "operator"]))
):
    """
    Delete a cloud credential securely.
    """
    svc = CredentialStoreService(db)
    try:
        svc.delete_credential(credential_id, user_id=current_user.id if current_user else None)
        return ApiResponse(
            success=True,
            data={"credential_id": credential_id},
            message="Cloud credential deleted successfully"
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete credential")


# ==============================================================================
# Storage Tiers Endpoints
# ==============================================================================

@storage_tiers_router.post(
    "",
    response_model=ApiResponse[StorageTierResponse],
    status_code=status.HTTP_201_CREATED
)
def create_tier(
    payload: StorageTierCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "operator"]))
):
    """
    Define a new Storage Tier in CREATED state.
    """
    manager = TieringManager(db)
    try:
        tier = manager.create_tier(
            name=payload.name,
            bucket=payload.bucket,
            provider=payload.provider,
            tier_type=payload.tier_type,
            credential_id=payload.credential_id,
            prefix=payload.prefix,
            object_lock_enabled=payload.object_lock_enabled,
            retention_period_days=payload.retention_period_days,
            immutability_mode=payload.immutability_mode,
            is_default=payload.is_default,
            user_id=current_user.id if current_user else None
        )
        return ApiResponse(
            success=True,
            data=StorageTierResponse.model_validate(tier),
            message=f"Storage tier '{tier.name}' created successfully in CREATED state"
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create storage tier: {str(e)}")


@storage_tiers_router.get(
    "",
    response_model=ApiResponse[List[StorageTierResponse]]
)
def list_tiers(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    List all storage tiers.
    """
    manager = TieringManager(db)
    tiers = manager.list_tiers()
    return ApiResponse(
        success=True,
        data=[StorageTierResponse.model_validate(t) for t in tiers],
        message=f"Retrieved {len(tiers)} storage tiers"
    )


@storage_tiers_router.get(
    "/{tier_id}",
    response_model=ApiResponse[StorageTierResponse]
)
def get_tier(
    tier_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Get detailed storage tier status and configuration.
    """
    manager = TieringManager(db)
    try:
        tier = manager.get_tier(tier_id)
        return ApiResponse(
            success=True,
            data=StorageTierResponse.model_validate(tier),
            message=f"Retrieved storage tier '{tier.name}'"
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@storage_tiers_router.patch(
    "/{tier_id}",
    response_model=ApiResponse[StorageTierResponse]
)
def update_tier(
    tier_id: str,
    payload: StorageTierUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "operator"]))
):
    """
    Update storage tier settings.
    """
    manager = TieringManager(db)
    try:
        updated = manager.update_tier(
            identifier=tier_id,
            name=payload.name,
            bucket=payload.bucket,
            prefix=payload.prefix,
            object_lock_enabled=payload.object_lock_enabled,
            retention_period_days=payload.retention_period_days,
            immutability_mode=payload.immutability_mode,
            is_enabled=payload.is_enabled,
            user_id=current_user.id if current_user else None
        )
        return ApiResponse(
            success=True,
            data=StorageTierResponse.model_validate(updated),
            message=f"Storage tier '{updated.name}' updated successfully"
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@storage_tiers_router.delete(
    "/{tier_id}",
    response_model=ApiResponse[dict]
)
def delete_tier(
    tier_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "operator"]))
):
    """
    Delete a storage tier.
    """
    manager = TieringManager(db)
    try:
        manager.delete_tier(tier_id, user_id=current_user.id if current_user else None)
        return ApiResponse(
            success=True,
            data={"tier_id": tier_id},
            message="Storage tier deleted successfully"
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@storage_tiers_router.post(
    "/{tier_id}/validate",
    response_model=ApiResponse[StorageTierValidateResponse]
)
def validate_tier(
    tier_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "operator"]))
):
    """
    Validate tier connectivity, credentials, and WORM Object Lock support.
    Transitions tier state from CREATED -> VALIDATING -> READY (or ERROR/DEGRADED).
    """
    manager = TieringManager(db)
    try:
        result = manager.validate_tier(tier_id)
        return ApiResponse(
            success=result["valid"],
            data=StorageTierValidateResponse(
                tier_id=result["tier_id"],
                state=result["state"],
                valid=result["valid"],
                latency_ms=result.get("latency_ms"),
                details=result.get("details"),
                error=result.get("error")
            ),
            message="Storage tier validation completed"
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Validation error: {str(e)}")


@storage_tiers_router.post(
    "/{tier_id}/offload",
    response_model=ApiResponse[OffloadResponse]
)
def offload_objects(
    tier_id: str,
    payload: OffloadRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "operator"]))
):
    """
    Safely offload CAS StorageObjects to the target storage tier.
    Performs COPY -> VERIFY -> RECORD. Local CAS data is never deleted or bypassed.
    """
    manager = TieringManager(db)
    try:
        res = manager.offload_objects(
            storage_object_ids=payload.storage_object_ids,
            tier_identifier=tier_id,
            user_id=current_user.id if current_user else None
        )
        items = []
        for s in res.get("successes", []):
            items.append(OffloadItemResponse(
                object_id=s["object_id"],
                offload_id=s["offload_id"],
                size=s["size"],
                status="VERIFIED"
            ))
        for f in res.get("failures", []):
            items.append(OffloadItemResponse(
                object_id=f["object_id"],
                status="FAILED",
                error=f["error"]
            ))

        return ApiResponse(
            success=res["failed_count"] == 0,
            data=OffloadResponse(
                total=res["total"],
                offloaded_count=res["offloaded_count"],
                failed_count=res["failed_count"],
                items=items
            ),
            message=f"Offloaded {res['offloaded_count']}/{res['total']} objects to tier"
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Offload error: {str(e)}")
