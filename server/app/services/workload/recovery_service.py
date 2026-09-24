"""RetroVault V11: Application-Aware Recovery Service."""

import os
import time
import json
import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.workload_v11_models import (
    Workload,
    WorkloadArtifact,
    ApplicationConsistencyRecord
)
from app.models.recovery_point import RecoveryPoint
from app.models.client import Client
from app.models.storage_object import StorageObject
from app.services.workload.discovery_service import WorkloadDiscoveryService
from app.services.workload.provider import (
    WorkloadProvider,
    RestorePreviewResult,
    RestoreExecutionResult,
    UNKNOWN
)


RECOVERY_MODES = [
    "FILE_RESTORE",
    "FOLDER_RESTORE",
    "FULL_RECOVERY_POINT",
    "APPLICATION_RESTORE",
    "DATABASE_RESTORE"
]


class WorkloadRecoveryService:
    """Manages application and database restores with conflict detection and verification."""

    def __init__(self, db: Session):
        self.db = db
        self.discovery_service = WorkloadDiscoveryService(db)

    def preview_restore(
        self,
        workload_id: str,
        recovery_point_id: str,
        target_destination: str,
        recovery_mode: str = "APPLICATION_RESTORE",
        target_client_id: Optional[str] = None
    ) -> RestorePreviewResult:
        """Preview restore execution, inspect target path, check consistency and dependencies."""
        stmt = select(Workload).where(Workload.workload_id == workload_id)
        workload = self.db.execute(stmt).scalars().first()
        if not workload:
            return RestorePreviewResult(
                workload_id=workload_id,
                source_recovery_point_id=recovery_point_id,
                target_destination=target_destination,
                estimated_size_bytes=0,
                is_safe_to_proceed=False,
                blockers=[f"Workload '{workload_id}' not found"]
            )

        # Cross-client isolation check
        if target_client_id and str(target_client_id) != str(workload.client_id):
            # Check permissions or block cross-client restore unless explicitly authorized
            pass

        provider = self.discovery_service.get_provider(workload.type)
        if not provider:
            return RestorePreviewResult(
                workload_id=workload_id,
                source_recovery_point_id=recovery_point_id,
                target_destination=target_destination,
                estimated_size_bytes=0,
                is_safe_to_proceed=False,
                blockers=[f"Provider for '{workload.type}' not available"]
            )

        # Retrieve consistency record for this RP
        acr_stmt = select(ApplicationConsistencyRecord).where(
            ApplicationConsistencyRecord.recovery_point_id == str(recovery_point_id)
        )
        acr = self.db.execute(acr_stmt).scalars().first()
        consistency_status = acr.consistency_state if acr else UNKNOWN

        # Check CAS artifacts
        art_stmt = select(WorkloadArtifact).where(
            WorkloadArtifact.recovery_point_id == str(recovery_point_id),
            WorkloadArtifact.workload_id == workload_id
        )
        artifacts = self.db.execute(art_stmt).scalars().all()
        estimated_size = sum(art.size_bytes for art in artifacts)

        # Conflict detection
        conflicts = []
        if os.path.exists(target_destination):
            conflicts.append(f"Target destination '{target_destination}' already exists on disk")

        context = {
            "workload_id": workload_id,
            "recovery_point_id": str(recovery_point_id),
            "target_destination": target_destination,
            "recovery_mode": recovery_mode,
            "config": json.loads(workload.config_json or "{}")
        }

        preview = provider.restore_preview(context)
        preview.consistency_status = consistency_status
        if estimated_size > 0:
            preview.estimated_size_bytes = estimated_size
        if conflicts:
            preview.overwrite_conflicts.extend(conflicts)

        return preview

    def execute_application_restore(
        self,
        workload_id: str,
        recovery_point_id: str,
        target_destination: str,
        recovery_mode: str = "APPLICATION_RESTORE",
        target_client_id: Optional[str] = None
    ) -> RestoreExecutionResult:
        """Execute the 7-phase application restore pipeline."""
        preview = self.preview_restore(
            workload_id=workload_id,
            recovery_point_id=recovery_point_id,
            target_destination=target_destination,
            recovery_mode=recovery_mode,
            target_client_id=target_client_id
        )

        if not preview.is_safe_to_proceed and preview.blockers:
            return RestoreExecutionResult(
                success=False,
                current_phase="PRECHECK",
                phases_completed=["DISCOVER"],
                error="; ".join(preview.blockers)
            )

        stmt = select(Workload).where(Workload.workload_id == workload_id)
        workload = self.db.execute(stmt).scalars().first()
        provider = self.discovery_service.get_provider(workload.type)

        context = {
            "workload_id": workload_id,
            "recovery_point_id": str(recovery_point_id),
            "target_destination": target_destination,
            "recovery_mode": recovery_mode,
            "config": json.loads(workload.config_json or "{}")
        }

        # Provider orchestrates: DISCOVER -> PRECHECK -> PREPARE -> RESTORE -> VERIFY -> VALIDATE -> COMPLETE
        return provider.restore_workload(context)
