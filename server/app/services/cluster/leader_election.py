"""Leader election service with lease-based consensus and split-brain protection for RetroVault V9."""

import datetime
import json
import logging
import uuid
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_

from app.models.cluster_v9_models import ClusterLease, ClusterNode, ClusterEvent

logger = logging.getLogger(__name__)


class LeaderElectionService:
    """Manages lease-based leader election, lease renewal, and leader failover."""

    DEFAULT_LEASE_TTL_SECONDS = 15

    def __init__(self, db: Session, lease_key: str = "LEADER_ELECTION"):
        self.db = db
        self.lease_key = lease_key

    def try_acquire_or_renew_leadership(
        self,
        node_id: str,
        ttl_seconds: Optional[int] = None
    ) -> Dict[str, Any]:
        """Atomically acquires leadership if unowned/expired, or renews if currently held by node_id."""
        ttl = ttl_seconds or self.DEFAULT_LEASE_TTL_SECONDS
        now = datetime.datetime.now(datetime.timezone.utc)
        expires_at = now + datetime.timedelta(seconds=ttl)
        token = uuid.uuid4().hex

        # Verify candidate node exists and is healthy
        node = self.db.query(ClusterNode).filter(ClusterNode.node_id == node_id).first()
        if not node or node.status in ["OFFLINE", "DRAINING", "MAINTENANCE"]:
            return {
                "is_leader": False,
                "error": f"Node {node_id} is ineligible for leadership (status={node.status if node else 'NONE'})",
                "leader_node_id": None
            }

        # Check if lease row exists
        lease = self.db.query(ClusterLease).filter(ClusterLease.lease_key == self.lease_key).first()

        if not lease:
            try:
                # Attempt to insert initial lease row
                lease = ClusterLease(
                    lease_key=self.lease_key,
                    owner_node_id=node_id,
                    lease_token=token,
                    lease_expires_at=expires_at,
                    acquired_at=now,
                    renewed_at=now,
                )
                self.db.add(lease)
                self.db.commit()
                self._log_event("LEADER_ELECTED", "INFO", node_id, {"ttl": ttl, "new_leader": True})
                return {
                    "is_leader": True,
                    "leader_node_id": node_id,
                    "lease_token": token,
                    "lease_expires_at": expires_at.isoformat(),
                    "action": "ACQUIRED"
                }
            except Exception:
                self.db.rollback()
                # Row was created concurrently by another node, continue to update logic below
                lease = self.db.query(ClusterLease).filter(ClusterLease.lease_key == self.lease_key).first()

        # Atomic Compare-And-Swap (CAS) update:
        # Acquire/renew ONLY IF current owner matches node_id OR lease has expired.
        # This guarantees strict mutual exclusion in PostgreSQL and SQLite under high concurrency.
        updated = (
            self.db.query(ClusterLease)
            .filter(
                ClusterLease.lease_key == self.lease_key,
                or_(
                    ClusterLease.owner_node_id == node_id,
                    ClusterLease.lease_expires_at < now
                )
            )
            .update({
                "owner_node_id": node_id,
                "lease_token": token,
                "lease_expires_at": expires_at,
                "renewed_at": now
            }, synchronize_session=False)
        )

        if updated > 0:
            self.db.commit()
            action = "RENEWED" if (lease and lease.owner_node_id == node_id) else "ACQUIRED_AFTER_EXPIRY"
            self._log_event(
                "LEADER_ELECTED" if action == "ACQUIRED_AFTER_EXPIRY" else "LEADER_RENEWED",
                "INFO",
                node_id,
                {"action": action, "ttl": ttl}
            )
            return {
                "is_leader": True,
                "leader_node_id": node_id,
                "lease_token": token,
                "lease_expires_at": expires_at.isoformat(),
                "action": action
            }

        # Another node holds a valid, active unexpired lease
        current_lease = self.db.query(ClusterLease).filter(ClusterLease.lease_key == self.lease_key).first()
        exp = current_lease.lease_expires_at if current_lease else now
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=datetime.timezone.utc)
        return {
            "is_leader": False,
            "leader_node_id": current_lease.owner_node_id if current_lease else None,
            "lease_expires_at": exp.isoformat(),
            "remaining_seconds": max(0, (exp - now).total_seconds()),
            "action": "DENIED"
        }

    def resign_leadership(self, node_id: str) -> Dict[str, Any]:
        """Voluntarily releases leadership (e.g. during planned draining or shutdown)."""
        lease = self.db.query(ClusterLease).filter(ClusterLease.lease_key == self.lease_key).first()
        if not lease or lease.owner_node_id != node_id:
            return {"resigned": False, "reason": "Node is not current leader"}

        now = datetime.datetime.now(datetime.timezone.utc)
        # Expire lease immediately to enable rapid failover
        lease.lease_expires_at = now - datetime.timedelta(seconds=1)
        self._log_event("LEADER_RESIGNED", "INFO", node_id, {"resigned_at": now.isoformat()})
        self.db.commit()
        return {"resigned": True, "node_id": node_id}

    def get_current_leader(self) -> Dict[str, Any]:
        """Returns the current active leader and validity status."""
        lease = self.db.query(ClusterLease).filter(ClusterLease.lease_key == self.lease_key).first()
        if not lease:
            return {"leader_node_id": None, "is_active": False}

        now = datetime.datetime.now(datetime.timezone.utc)
        lease_exp = lease.lease_expires_at
        if lease_exp.tzinfo is None:
            lease_exp = lease_exp.replace(tzinfo=datetime.timezone.utc)

        is_active = now <= lease_exp
        return {
            "leader_node_id": lease.owner_node_id if is_active else None,
            "is_active": is_active,
            "lease_expires_at": lease_exp.isoformat(),
            "last_leader": lease.owner_node_id
        }

    def _log_event(self, event_type: str, severity: str, node_id: str, details: Dict[str, Any]):
        ev = ClusterEvent(
            event_type=event_type,
            severity=severity,
            node_id=node_id,
            details_json=json.dumps(details),
        )
        self.db.add(ev)
