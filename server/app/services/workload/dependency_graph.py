"""RetroVault V11: Advanced Dependency Graph & Safety Invariants Engine."""

import datetime
from typing import Dict, Any, List, Optional, Set
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.models.workload_v11_models import (
    DependencyRelation,
    Workload,
    WorkloadArtifact,
    RecoveryVerification,
    BackupChain
)
from app.models.recovery_point import RecoveryPoint
from app.models.storage_object import StorageObject
from app.models.replication import ReplicationJob


class DependencyGraphEngine:
    """Maintains logical relationships and prevents unsafe deletion or orphan purges."""

    def __init__(self, db: Session):
        self.db = db

    def register_dependency(
        self,
        parent_type: str,
        parent_id: str,
        child_type: str,
        child_id: str,
        relation_type: str = "REQUIRES"
    ) -> DependencyRelation:
        """Register a directional parent->child dependency relation."""
        now = datetime.datetime.now(datetime.timezone.utc)
        stmt = select(DependencyRelation).where(
            DependencyRelation.parent_type == parent_type,
            DependencyRelation.parent_id == str(parent_id),
            DependencyRelation.child_type == child_type,
            DependencyRelation.child_id == str(child_id)
        )
        existing = self.db.execute(stmt).scalars().first()
        if existing:
            return existing

        dep = DependencyRelation(
            parent_type=parent_type,
            parent_id=str(parent_id),
            child_type=child_type,
            child_id=str(child_id),
            relation_type=relation_type,
            created_at=now
        )
        self.db.add(dep)
        self.db.commit()
        self.db.refresh(dep)
        return dep

    def verify_safe_to_delete(self, resource_type: str, resource_id: str) -> Dict[str, Any]:
        """Examine dependency tree to verify if a resource can be safely deleted without cascade damage."""
        blockers = []

        if resource_type.upper() == "CAS_OBJECT":
            # Check StorageObject reference count and dependent recovery points
            so_stmt = select(StorageObject).where(StorageObject.object_id == resource_id)
            so = self.db.execute(so_stmt).scalars().first()
            if so and so.reference_count > 1:
                blockers.append(f"StorageObject '{resource_id}' has {so.reference_count} active references across recovery points")

            art_stmt = select(WorkloadArtifact).where(WorkloadArtifact.storage_object_id == resource_id)
            arts = self.db.execute(art_stmt).scalars().all()
            if len(arts) > 0:
                blockers.append(f"Referenced by {len(arts)} workload artifact(s) in active recovery points")

        elif resource_type.upper() == "RECOVERY_POINT":
            rp_stmt = select(RecoveryPoint).where(RecoveryPoint.id == int(resource_id))
            rp = self.db.execute(rp_stmt).scalars().first()
            if rp:
                # Security Hold Check (V8 Integration)
                if rp.protection_state == "SECURITY_HOLD":
                    blockers.append(f"RecoveryPoint {resource_id} is under active SECURITY_HOLD (Ransomware protection invariant)")

                # Check if it's the base of a backup chain
                chain_stmt = select(BackupChain).where(BackupChain.base_recovery_point_id == str(resource_id))
                chains = self.db.execute(chain_stmt).scalars().all()
                if chains:
                    blockers.append(f"RecoveryPoint {resource_id} is the base of active backup chain '{chains[0].chain_id}'")

        elif resource_type.upper() == "WORKLOAD":
            # Check if active protections or unexpired recovery points exist
            rp_stmt = select(WorkloadArtifact).where(WorkloadArtifact.workload_id == resource_id)
            arts = self.db.execute(rp_stmt).scalars().all()
            if len(arts) > 0:
                blockers.append(f"Workload {resource_id} has {len(arts)} retained backup artifact(s) in repository")

        is_safe = (len(blockers) == 0)
        return {
            "resource_type": resource_type,
            "resource_id": str(resource_id),
            "is_safe_to_delete": is_safe,
            "blockers": blockers
        }

    def get_dependencies_for(self, resource_type: str, resource_id: str) -> List[Dict[str, Any]]:
        """Query children and dependents of a given node in the graph."""
        stmt = select(DependencyRelation).where(
            DependencyRelation.parent_type == resource_type,
            DependencyRelation.parent_id == str(resource_id)
        )
        deps = self.db.execute(stmt).scalars().all()
        return [
            {
                "child_type": d.child_type,
                "child_id": d.child_id,
                "relation_type": d.relation_type,
                "created_at": d.created_at.isoformat()
            }
            for d in deps
        ]
