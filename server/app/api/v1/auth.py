import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, RefreshTokenRequest, UserResponse
from app.schemas.common import ApiResponse
from app.security.password import verify_password
from app.security.jwt import create_access_token, create_refresh_token, decode_token
from app.security.dependencies import get_current_user
from app.services.audit_service import log_audit_event
from app.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=ApiResponse[TokenResponse])
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == request.username).first()
    if not user or not verify_password(request.password, user.password_hash):
        log_audit_event(
            db=db,
            action="LOGIN_FAILED",
            resource_type="auth",
            details=f"Failed login attempt for username: {request.username}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled"
        )

    access_token = create_access_token(
        data={"sub": user.username, "role": user.role, "user_id": user.id}
    )
    refresh_token = create_refresh_token(
        data={"sub": user.username}
    )

    log_audit_event(
        db=db,
        action="LOGIN_SUCCESS",
        resource_type="auth",
        user_id=user.id,
        details=f"User {user.username} logged in successfully with role {user.role}"
    )

    token_data = TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_id=user.id,
        username=user.username,
        role=user.role
    )

    return ApiResponse(
        success=True,
        data=token_data,
        message="Authentication successful"
    )

@router.post("/refresh", response_model=ApiResponse[dict])
def refresh_token(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    payload = decode_token(request.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )

    username = payload.get("sub")
    user = db.query(User).filter(User.username == username, User.is_active == True).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer active or valid"
        )

    new_access_token = create_access_token(
        data={"sub": user.username, "role": user.role, "user_id": user.id}
    )

    return ApiResponse(
        success=True,
        data={"access_token": new_access_token, "token_type": "bearer"},
        message="Token refreshed successfully"
    )

@router.get("/me", response_model=ApiResponse[UserResponse])
def get_me(current_user: User = Depends(get_current_user)):
    return ApiResponse(
        success=True,
        data=UserResponse.model_validate(current_user),
        message="Current user profile retrieved"
    )
