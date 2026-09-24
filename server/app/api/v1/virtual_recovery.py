"""Instant Virtual Recovery API router for RetroVault V12."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.v12_ivr_schemas import (
    VirtualRecoverySessionCreate,
    VirtualRecoverySessionResponse,
    PrefetchRequest,
    HydrationRequest,
    VirtualRecoveryMetricsResponse
)
from app.security.dependencies import require_role, get_optional_current_user
from app.services.v12.virtual_recovery.session_manager import VirtualRecoverySessionManager
from app.services.v12.virtual_recovery.provider_base import (
    SessionStateError,
    VirtualRecoveryError
)

router = APIRouter(prefix="/virtual-recovery/sessions", tags=["Instant Virtual Recovery"])


@router.post("", response_model=ApiResponse[VirtualRecoverySessionResponse], status_code=status.HTTP_201_CREATED)
def create_session(
    payload: VirtualRecoverySessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "operator"]))
):
    """
    Creates an Instant Virtual Recovery session for a valid Recovery Point.
    Enforces active recovery protection preventing GC and retention prune.
    """
    manager = VirtualRecoverySessionManager(db)
    try:
        session = manager.create_session(
            recovery_point_id=payload.recovery_point_id,
            target_path=payload.target_path,
            client_id=payload.client_id,
            workload_id=payload.workload_id,
            cloud_tier_id=payload.cloud_tier_id,
            provider_type=payload.provider_type,
            user_id=current_user.id if current_user else None
        )
        return ApiResponse(
            success=True,
            data=VirtualRecoverySessionResponse.model_validate(session),
            message=f"Virtual recovery session '{session.session_id}' created successfully"
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create session: {str(e)}")


@router.get("", response_model=ApiResponse[List[VirtualRecoverySessionResponse]])
def list_sessions(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    List all virtual recovery sessions.
    """
    manager = VirtualRecoverySessionManager(db)
    sessions = manager.list_sessions()
    return ApiResponse(
        success=True,
        data=[VirtualRecoverySessionResponse.model_validate(s) for s in sessions],
        message=f"Retrieved {len(sessions)} virtual recovery sessions"
    )


@router.get("/{id}", response_model=ApiResponse[VirtualRecoverySessionResponse])
def get_session(
    id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Get virtual recovery session details and status.
    """
    manager = VirtualRecoverySessionManager(db)
    try:
        session = manager.get_session(id)
        return ApiResponse(
            success=True,
            data=VirtualRecoverySessionResponse.model_validate(session),
            message=f"Retrieved virtual recovery session '{session.session_id}'"
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{id}/prepare", response_model=ApiResponse[dict])
def prepare_session(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "operator"]))
):
    """
    Pre-flight preparation: traverses recovery point manifest and initializes hydration tracking.
    """
    manager = VirtualRecoverySessionManager(db)
    try:
        res = manager.prepare_session(id)
        return ApiResponse(success=True, data=res, message="Session prepared successfully")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except SessionStateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{id}/mount", response_model=ApiResponse[dict])
def mount_session(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "operator"]))
):
    """
    Instantly mounts target filesystem stubs for immediate browsing and read access.
    """
    manager = VirtualRecoverySessionManager(db)
    try:
        res = manager.mount_session(id)
        return ApiResponse(success=True, data=res, message="Session mounted successfully for instant access")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except SessionStateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{id}/prefetch", response_model=ApiResponse[dict])
def prefetch_files(
    id: str,
    payload: PrefetchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "operator"]))
):
    """
    Prefetches selected high-priority files (e.g., boot/db) into the bounded cache.
    """
    manager = VirtualRecoverySessionManager(db)
    try:
        res = manager.prefetch(id, payload.paths)
        return ApiResponse(success=True, data=res, message="Prefetch operation completed")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{id}/hydrate", response_model=ApiResponse[dict])
def hydrate_session(
    id: str,
    payload: Optional[HydrationRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "operator"]))
):
    """
    Executes or resumes background hydration of physical data into the target path.
    """
    manager = VirtualRecoverySessionManager(db)
    max_files = payload.max_files if payload else None
    try:
        res = manager.hydrate(id, max_files=max_files)
        return ApiResponse(success=True, data=res, message="Hydration progressed successfully")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{id}/pause", response_model=ApiResponse[dict])
def pause_hydration(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "operator"]))
):
    """
    Pauses ongoing background hydration.
    """
    manager = VirtualRecoverySessionManager(db)
    try:
        res = manager.pause_hydration(id)
        return ApiResponse(success=True, data=res, message="Hydration paused")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{id}/resume", response_model=ApiResponse[dict])
def resume_hydration(
    id: str,
    payload: Optional[HydrationRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "operator"]))
):
    """
    Resumes paused background hydration.
    """
    manager = VirtualRecoverySessionManager(db)
    max_files = payload.max_files if payload else None
    try:
        res = manager.resume_hydration(id, max_files=max_files)
        return ApiResponse(success=True, data=res, message="Hydration resumed")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{id}/unmount", response_model=ApiResponse[dict])
def unmount_session(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "operator"]))
):
    """
    Safely detaches virtual recovery mount and releases Recovery Point protection.
    """
    manager = VirtualRecoverySessionManager(db)
    try:
        manager.unmount_session(id, user_id=current_user.id if current_user else None)
        return ApiResponse(success=True, data={"session_id": id}, message="Session unmounted successfully")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{id}/cancel", response_model=ApiResponse[dict])
def cancel_session(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "operator"]))
):
    """
    Cancels virtual recovery session and frees active protection lock.
    """
    manager = VirtualRecoverySessionManager(db)
    try:
        manager.cancel_session(id, user_id=current_user.id if current_user else None)
        return ApiResponse(success=True, data={"session_id": id}, message="Session cancelled successfully")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{id}/metrics", response_model=ApiResponse[VirtualRecoveryMetricsResponse])
def get_metrics(
    id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Get granular RTO and operation metrics for the session.
    """
    manager = VirtualRecoverySessionManager(db)
    try:
        metrics = manager.get_session_metrics(id)
        return ApiResponse(
            success=True,
            data=VirtualRecoveryMetricsResponse(**metrics),
            message="Retrieved session metrics"
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
