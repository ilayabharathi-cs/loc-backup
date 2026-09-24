"""Distributed lock service with crash-safe expiration for RetroVault V9."""

import datetime
import uuid
import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.cluster_v9_models import DistributedLock

logger = logging.getLogger(__name__)


class DistributedLockService:
    """Manages distributed locks across cluster nodes with expiration TTLs."""

    DEFAULT_LOCK_TTL_SECONDS = 60

    def __init__(self, db: Session):
        self.db = db

    def acquire_lock(
        self,
        resource_key: str,
        owner_node_id: str,
        lock_type: str = "BACKUP_RUN",
        ttl_seconds: Optional[int] = None
    ) -> Dict[str, Any]:
        """Attempts to acquire a distributed lock for a resource."""
        ttl = ttl_seconds or self.DEFAULT_LOCK_TTL_SECONDS
        now = datetime.datetime.now(datetime.timezone.utc)
        expires_at = now + datetime.timedelta(seconds=ttl)
        token = uuid.uuid4().hex

        lock = self.db.query(DistributedLock).filter(DistributedLock.resource_key == resource_key).first()

        if not lock:
            try:
                lock = DistributedLock(
                    resource_key=resource_key,
                    lock_type=lock_type,
                    owner_node_id=owner_node_id,
                    lock_token=token,
                    expires_at=expires_at,
                    acquired_at=now,
                )
                self.db.add(lock)
                self.db.commit()
                return {"acquired": True, "token": token, "resource_key": resource_key, "expires_at": expires_at.isoformat()}
            except Exception:
                self.db.rollback()
                lock = self.db.query(DistributedLock).filter(DistributedLock.resource_key == resource_key).first()

        # Atomic Compare-And-Swap (CAS) update:
        # Re-acquire expired lock or refresh lock owned by owner_node_id
        from sqlalchemy import or_
        updated = (
            self.db.query(DistributedLock)
            .filter(
                DistributedLock.resource_key == resource_key,
                or_(
                    DistributedLock.owner_node_id == owner_node_id,
                    DistributedLock.expires_at < now
                )
            )
            .update({
                "owner_node_id": owner_node_id,
                "lock_token": token,
                "lock_type": lock_type,
                "expires_at": expires_at,
                "acquired_at": now
            }, synchronize_session=False)
        )

        if updated > 0:
            self.db.commit()
            return {"acquired": True, "token": token, "resource_key": resource_key, "expires_at": expires_at.isoformat()}

        # Active lock already held by another unexpired node
        current_lock = self.db.query(DistributedLock).filter(DistributedLock.resource_key == resource_key).first()
        exp = current_lock.expires_at if current_lock else now
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=datetime.timezone.utc)

        return {
            "acquired": False,
            "owner_node_id": current_lock.owner_node_id if current_lock else None,
            "expires_at": exp.isoformat(),
            "resource_key": resource_key
        }

    def renew_lock(self, resource_key: str, lock_token: str, ttl_seconds: Optional[int] = None) -> bool:
        """Renews an active lock held by lock_token."""
        ttl = ttl_seconds or self.DEFAULT_LOCK_TTL_SECONDS
        now = datetime.datetime.now(datetime.timezone.utc)
        expires_at = now + datetime.timedelta(seconds=ttl)

        lock = (
            self.db.query(DistributedLock)
            .filter(DistributedLock.resource_key == resource_key, DistributedLock.lock_token == lock_token)
            .first()
        )
        if not lock:
            return False

        lock.expires_at = expires_at
        self.db.commit()
        return True

    def release_lock(self, resource_key: str, lock_token: str) -> bool:
        """Explicitly releases a lock held by lock_token."""
        lock = (
            self.db.query(DistributedLock)
            .filter(DistributedLock.resource_key == resource_key, DistributedLock.lock_token == lock_token)
            .first()
        )
        if not lock:
            return False

        self.db.delete(lock)
        self.db.commit()
        return True

    def is_locked(self, resource_key: str) -> bool:
        """Checks if a resource is currently locked by a valid unexpired lease."""
        lock = self.db.query(DistributedLock).filter(DistributedLock.resource_key == resource_key).first()
        if not lock:
            return False

        now = datetime.datetime.now(datetime.timezone.utc)
        lock_exp = lock.expires_at
        if lock_exp.tzinfo is None:
            lock_exp = lock_exp.replace(tzinfo=datetime.timezone.utc)

        return now <= lock_exp
