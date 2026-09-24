from typing import List, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.user import User
from app.security.jwt import decode_token

security_scheme = HTTPBearer(auto_error=False)

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials or token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    username: Optional[str] = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account"
        )

    return user

ROLE_PERMISSIONS = {
    "admin": ["*"],
    "ADMIN": ["*"],
    "operator": [
        "clients.read", "clients.manage", "policies.read", "policies.manage",
        "backup.execute", "restore.execute", "repositories.read", "repositories.manage",
        "replication.read", "replication.execute", "audit.read", "dr.execute", "dr.read", "alerts.manage"
    ],
    "OPERATOR": [
        "clients.read", "clients.manage", "policies.read", "policies.manage",
        "backup.execute", "restore.execute", "repositories.read", "repositories.manage",
        "replication.read", "replication.execute", "audit.read", "dr.execute", "dr.read", "alerts.manage"
    ],
    "auditor": [
        "audit.read", "security.manage", "clients.read", "repositories.read",
        "policies.read", "replication.read", "dr.read"
    ],
    "AUDITOR": [
        "audit.read", "security.manage", "clients.read", "repositories.read",
        "policies.read", "replication.read", "dr.read"
    ],
    "viewer": [
        "clients.read", "policies.read", "repositories.read", "audit.read",
        "replication.read", "dr.read"
    ],
    "VIEWER": [
        "clients.read", "policies.read", "repositories.read", "audit.read",
        "replication.read", "dr.read"
    ],
}

def user_has_permission(role: str, permission: str) -> bool:
    perms = ROLE_PERMISSIONS.get(role, [])
    if "*" in perms:
        return True
    return permission in perms

def require_permission(required_perm: str):
    def perm_checker(current_user: User = Depends(get_current_user)) -> User:
        if not user_has_permission(current_user.role, required_perm):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Missing required permission '{required_perm}'"
            )
        return current_user
    return perm_checker

def require_role(allowed_roles: List[str]):
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_role_lower = current_user.role.lower()
        allowed_lower = [r.lower() for r in allowed_roles]
        if user_role_lower not in allowed_lower:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Requires one of roles: {', '.join(allowed_roles)}"
            )
        return current_user
    return role_checker

def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> Optional[User]:
    if not credentials:
        return None
    try:
        return get_current_user(credentials, db)
    except HTTPException:
        return None
