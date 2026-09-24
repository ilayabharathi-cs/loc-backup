"""Node registration and heartbeat service for RetroVault V9 Cluster."""

import datetime
import json
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.cluster_v9_models import ClusterNode, ClusterEvent

logger = logging.getLogger(__name__)


class NodeHeartbeatService:
    """Manages cluster node lifecycle, heartbeats, draining, and failure detection."""

    DEFAULT_STALE_SECONDS = 30
    DEFAULT_OFFLINE_SECONDS = 90

    def __init__(self, db: Session):
        self.db = db

    def register_node(
        self,
        node_id: str,
        hostname: str,
        ip_address: str,
        role: Any = "CONTROL_PLANE",
        roles: Optional[List[str]] = None,
        capabilities: Optional[Dict[str, bool]] = None,
        version: str = "9.0.0",
        port: int = 8000,
        capacity_weight: int = 1,
        max_concurrent_jobs: int = 4,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ClusterNode:
        """Registers a new node or marks an existing node active upon startup."""
        now = datetime.datetime.now(datetime.timezone.utc)
        node = self.db.query(ClusterNode).filter(ClusterNode.node_id == node_id).first()

        # Handle list vs string role
        effective_roles = roles or ([role] if isinstance(role, str) else list(role) if isinstance(role, (list, tuple)) else ["CONTROL_PLANE"])
        primary_role = str(effective_roles[0]).upper() if effective_roles else "CONTROL_PLANE"

        caps_str = json.dumps(capabilities or {
            "scheduler": "CONTROL_PLANE" in effective_roles or "SCHEDULER" in effective_roles,
            "backup_worker": "WORKER" in effective_roles or "REPOSITORY_WORKER" in effective_roles,
            "restore_worker": "WORKER" in effective_roles or "REPOSITORY_WORKER" in effective_roles,
            "replication_worker": "WORKER" in effective_roles or "REPOSITORY_WORKER" in effective_roles,
            "gc_worker": "WORKER" in effective_roles or "REPOSITORY_WORKER" in effective_roles,
            "integrity_worker": "WORKER" in effective_roles or "REPOSITORY_WORKER" in effective_roles,
        })

        if not node:
            node = ClusterNode(
                node_id=node_id,
                hostname=hostname,
                ip_address=ip_address,
                role=primary_role,
                status="HEALTHY",
                version=version,
                capabilities_json=caps_str,
                last_heartbeat=now,
                started_at=now,
            )
            self.db.add(node)
            self._log_event("NODE_JOINED", "INFO", node_id, {"role": primary_role, "ip": ip_address, "port": port})
        else:
            node.hostname = hostname
            node.ip_address = ip_address
            node.role = primary_role
            node.status = "HEALTHY"
            node.version = version
            node.capabilities_json = caps_str
            node.last_heartbeat = now
            node.draining_started_at = None
            self._log_event("NODE_JOINED", "INFO", node_id, {"reconnected": True, "status": "HEALTHY"})

        self.db.commit()
        self.db.refresh(node)
        return node

    def record_heartbeat(self, node_id: str, status_override: Optional[str] = None) -> Dict[str, Any]:
        """Updates last_heartbeat for an active node."""
        node = self.db.query(ClusterNode).filter(ClusterNode.node_id == node_id).first()
        if not node:
            return {"error": f"Node {node_id} not registered", "success": False}

        now = datetime.datetime.now(datetime.timezone.utc)
        node.last_heartbeat = now

        if status_override:
            node.status = status_override.upper()
        elif node.status == "OFFLINE" or node.status == "STARTING":
            node.status = "HEALTHY"

        self.db.commit()
        return {"node_id": node_id, "status": node.status, "last_heartbeat": now.isoformat(), "success": True}

    def heartbeat_node(
        self,
        node_id: str,
        current_load: float = 0.0,
        active_jobs_count: int = 0,
        metrics: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Alias for heartbeat probe from REST API."""
        res = self.record_heartbeat(node_id)
        return res.get("success", False)

    def set_draining(self, node_id: str) -> Dict[str, Any]:
        """Sets a node into DRAINING status for graceful zero-downtime maintenance."""
        node = self.db.query(ClusterNode).filter(ClusterNode.node_id == node_id).first()
        if not node:
            return {"error": f"Node {node_id} not found", "success": False, "updated": False}

        now = datetime.datetime.now(datetime.timezone.utc)
        node.status = "DRAINING"
        node.draining_started_at = now
        self._log_event("NODE_DRAINING", "WARNING", node_id, {"draining_started_at": now.isoformat()})
        self.db.commit()
        return {"node_id": node_id, "status": "DRAINING", "success": True, "updated": True}

    def set_node_draining(self, node_id: str, draining: bool = True) -> Dict[str, Any]:
        """Toggles draining mode on or off."""
        if draining:
            return self.set_draining(node_id)
        
        node = self.db.query(ClusterNode).filter(ClusterNode.node_id == node_id).first()
        if not node:
            return {"error": f"Node {node_id} not found", "success": False, "updated": False}
        
        node.status = "HEALTHY"
        node.draining_started_at = None
        self.db.commit()
        return {"node_id": node_id, "status": "HEALTHY", "success": True, "updated": True}

    def deregister_node(self, node_id: str) -> Dict[str, Any]:
        """Removes or marks node OFFLINE."""
        node = self.db.query(ClusterNode).filter(ClusterNode.node_id == node_id).first()
        if not node:
            return {"error": f"Node {node_id} not found", "deregistered": False}
        
        node.status = "OFFLINE"
        self._log_event("NODE_LEFT", "INFO", node_id, {"reason": "Deregistered"})
        self.db.commit()
        return {"node_id": node_id, "deregistered": True}

    def list_nodes(self, active_only: bool = False) -> List[ClusterNode]:
        """Lists cluster nodes."""
        query = self.db.query(ClusterNode)
        if active_only:
            query = query.filter(ClusterNode.status.in_(["HEALTHY", "ACTIVE", "READY"]))
        return query.order_by(ClusterNode.id.asc()).all()

    def set_maintenance(self, node_id: str) -> Dict[str, Any]:
        """Sets a node to MAINTENANCE mode after active operations have finished draining."""
        node = self.db.query(ClusterNode).filter(ClusterNode.node_id == node_id).first()
        if not node:
            return {"error": f"Node {node_id} not found", "success": False}

        node.status = "MAINTENANCE"
        self._log_event("NODE_OFFLINE", "INFO", node_id, {"reason": "Maintenance mode entered"})
        self.db.commit()
        return {"node_id": node_id, "status": "MAINTENANCE", "success": True}

    def detect_stale_and_offline_nodes(
        self,
        stale_seconds: Optional[int] = None,
        offline_seconds: Optional[int] = None
    ) -> Dict[str, Any]:
        """Evaluates all registered nodes and transitions stale nodes to DEGRADED or OFFLINE."""
        stale_sec = stale_seconds or self.DEFAULT_STALE_SECONDS
        offline_sec = offline_seconds or self.DEFAULT_OFFLINE_SECONDS

        now = datetime.datetime.now(datetime.timezone.utc)
        nodes = self.db.query(ClusterNode).filter(ClusterNode.status.in_(["HEALTHY", "DEGRADED", "DRAINING"])).all()

        degraded_count = 0
        offline_count = 0
        updated_nodes = []

        for node in nodes:
            hb = node.last_heartbeat
            if hb.tzinfo is None:
                hb = hb.replace(tzinfo=datetime.timezone.utc)

            delta = (now - hb).total_seconds()

            if delta >= offline_sec:
                node.status = "OFFLINE"
                offline_count += 1
                updated_nodes.append({"node_id": node.node_id, "new_status": "OFFLINE", "missed_seconds": delta})
                self._log_event("NODE_OFFLINE", "ERROR", node.node_id, {"missed_seconds": delta})
            elif delta >= stale_sec and node.status == "HEALTHY":
                node.status = "DEGRADED"
                degraded_count += 1
                updated_nodes.append({"node_id": node.node_id, "new_status": "DEGRADED", "missed_seconds": delta})
                self._log_event("NODE_HEARTBEAT", "WARNING", node.node_id, {"reason": "Stale heartbeat detected", "missed_seconds": delta})

        self.db.commit()
        return {
            "evaluated_count": len(nodes),
            "degraded_count": degraded_count,
            "offline_count": offline_count,
            "updates": updated_nodes
        }

    def reap_offline_nodes(self, timeout_seconds: int = 30) -> Dict[str, Any]:
        """Convenience method for cluster leader reconciliation."""
        return self.detect_stale_and_offline_nodes(stale_seconds=timeout_seconds, offline_seconds=timeout_seconds * 2)

    def _log_event(self, event_type: str, severity: str, node_id: Optional[str], details: Dict[str, Any]):
        ev = ClusterEvent(
            event_type=event_type,
            severity=severity,
            node_id=node_id,
            details_json=json.dumps(details),
        )
        self.db.add(ev)
