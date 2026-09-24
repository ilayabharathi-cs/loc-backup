"""RetroVault V11: Workload Protection Execution Service."""

import os
import time
import json
import uuid
import datetime
import hashlib
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.workload_v11_models import (
    Workload,
    WorkloadArtifact,
    ApplicationConsistencyRecord,
    BackupChain
)
from app.models.storage_object import StorageObject
from app.models.recovery_point import RecoveryPoint
from app.models.client import Client
from app.models.backup_run import BackupRun
from app.models.backup_job import BackupJob
from app.models.observability_v10_models import MetricSample, ComplianceEvidence
from app.services.workload.discovery_service import WorkloadDiscoveryService
from app.services.workload.consistency_service import WorkloadConsistencyService
from app.services.workload.provider import (
    WorkloadProvider,
    HookResult,
    QuiesceResult,
    BackupArtifactResult,
    ConsistencyResult,
    APPLICATION_CONSISTENT,
    FILE_SYSTEM_CONSISTENT,
    CRASH_CONSISTENT,
    FAILED,
    STATUS_PREPARING,
    STATUS_QUIESCING,
    STATUS_BACKING_UP,
    STATUS_VERIFYING,
    STATUS_COMPLETING,
    STATUS_COMPLETED,
    STATUS_FAILED
)


class WorkloadProtectionService:
    """Executes capability-driven, application-consistent backups for registered workloads."""

    def __init__(self, db: Session):
        self.db = db
        self.discovery_service = WorkloadDiscoveryService(db)
        self.consistency_service = WorkloadConsistencyService(db)

    def execute_workload_backup(
        self,
        workload_id: str,
        backup_type: str = "FULL",  # FULL, LOG, INCREMENTAL
        initiated_by: str = "SYSTEM",
        context_override: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Orchestrate the full application-aware backup workflow."""
        start_time = time.perf_counter()
        now = datetime.datetime.now(datetime.timezone.utc)

        # 1. Fetch workload
        stmt = select(Workload).where(Workload.workload_id == workload_id)
        workload = self.db.execute(stmt).scalars().first()
        if not workload:
            return {"success": False, "error": f"Workload '{workload_id}' not found"}

        provider: Optional[WorkloadProvider] = self.discovery_service.get_provider(workload.type)
        if not provider:
            workload.status = STATUS_FAILED
            self.db.commit()
            return {"success": False, "error": f"Provider for '{workload.type}' not available"}

        config = json.loads(workload.config_json or "{}")
        if context_override:
            config.update(context_override)

        context = {
            "workload_id": workload.workload_id,
            "client_id": workload.client_id,
            "config": config,
            "backup_type": backup_type,
            "initiated_by": initiated_by
        }

        # Step A: Preparing & Pre-snapshot hook
        workload.status = STATUS_PREPARING
        self.db.commit()

        pre_hook_res: HookResult = provider.pre_snapshot_hook(context)
        context["pre_hook_result"] = pre_hook_res
        if not pre_hook_res.success:
            workload.status = STATUS_FAILED
            self._record_telemetry(workload, "workload_backup_failures", 1.0)
            self._record_telemetry(workload, "application_consistency_failures", 1.0)
            self.db.commit()
            return {
                "success": False,
                "status": STATUS_FAILED,
                "error": f"Pre-snapshot hook failed: {pre_hook_res.error}",
                "evidence": pre_hook_res.evidence
            }

        # Step B: Quiescing
        workload.status = STATUS_QUIESCING
        self.db.commit()

        quiesce_res: QuiesceResult = provider.quiesce(context)
        context["quiesce_result"] = quiesce_res

        # Step C: Snapshot / Application Backup
        workload.status = STATUS_BACKING_UP
        self.db.commit()

        backup_res: BackupArtifactResult = provider.snapshot_backup(context)
        context["artifacts"] = backup_res.artifacts

        # Step D: Unquiescing (ALWAYS executed after snapshot, even if snapshot errored)
        unquiesce_res: HookResult = provider.unquiesce(context)
        context["unquiesce_result"] = unquiesce_res

        # Step E: Post-snapshot hook
        post_hook_res: HookResult = provider.post_snapshot_hook(context)
        context["post_hook_result"] = post_hook_res

        # Step F: Verify Consistency
        workload.status = STATUS_VERIFYING
        self.db.commit()

        consistency_res: ConsistencyResult = provider.verify_consistency(context)

        # Step G: Persist artifacts to CAS / StorageObjects
        workload.status = STATUS_COMPLETING
        self.db.commit()

        total_bytes = 0
        persisted_artifacts: List[WorkloadArtifact] = []

        # Find or create a matching RecoveryPoint
        rp = self._ensure_recovery_point(workload, backup_type, now)

        for art in backup_res.artifacts:
            art_id = art["artifact_id"]
            data_content = art.get("data_content", b"")
            sha256 = art["checksum_sha256"]
            size_bytes = art["size_bytes"]
            total_bytes += size_bytes

            # Check or create StorageObject in CAS
            storage_obj_id = self._ensure_cas_storage_object(sha256, size_bytes, data_content)

            w_art = WorkloadArtifact(
                artifact_id=art_id,
                workload_id=workload.workload_id,
                recovery_point_id=str(rp.id),
                artifact_name=art["artifact_name"],
                artifact_type=art["artifact_type"],
                storage_object_id=storage_obj_id,
                size_bytes=size_bytes,
                checksum_sha256=sha256,
                artifact_metadata_json=json.dumps(art.get("metadata", {})),
                created_at=now
            )
            self.db.add(w_art)
            persisted_artifacts.append(w_art)

        # Step H: Record Consistency Record
        consistency_rec = self.consistency_service.evaluate_and_record_consistency(
            recovery_point_id=str(rp.id),
            workload_id=workload.workload_id,
            consistency_result=consistency_res,
            verified_by=initiated_by
        )

        # Step I: Update Backup Chain
        chain = self._update_backup_chain(workload, rp, backup_type, now)

        # Step J: Finalize Workload & Recovery Point
        duration_total = (time.perf_counter() - start_time) * 1000.0
        workload.status = STATUS_COMPLETED
        workload.last_protected_at = now
        workload.protection_state = "PROTECTED"
        workload.consistency_capability = consistency_rec.consistency_state

        rp.total_size_bytes = total_bytes
        rp.files_count = len(persisted_artifacts)

        # Telemetry & Compliance
        self._record_telemetry(workload, "workload_backup_duration", duration_total)
        self._record_telemetry(workload, "workload_backup_bytes", float(total_bytes))
        self._record_compliance(workload, rp, consistency_rec)

        self.db.commit()

        return {
            "success": True,
            "status": STATUS_COMPLETED,
            "workload_id": workload.workload_id,
            "recovery_point_id": rp.id,
            "consistency_state": consistency_rec.consistency_state,
            "artifacts_count": len(persisted_artifacts),
            "total_bytes": total_bytes,
            "duration_ms": duration_total,
            "chain_id": chain.chain_id if chain else None
        }

    def _ensure_recovery_point(self, workload: Workload, backup_type: str, now: datetime.datetime) -> RecoveryPoint:
        """Find or create an active RecoveryPoint for this backup."""
        client_id_val = 1
        try:
            stmt = select(Client).where(Client.id == workload.client_id)
            c = self.db.execute(stmt).scalars().first()
            if c:
                client_id_val = c.id
        except Exception:
            client_id_val = 1

        # Find or create a default BackupRun
        run_stmt = select(BackupRun).order_by(BackupRun.id.desc())
        run = self.db.execute(run_stmt).scalars().first()
        run_id = run.id if run else 1

        rp = RecoveryPoint(
            client_id=client_id_val,
            backup_run_id=run_id,
            backup_type=backup_type.lower(),
            timestamp=now,
            files_count=0,
            total_size_bytes=0,
            status="valid",
            retention_status="active",
            protection_state="NORMAL"
        )
        self.db.add(rp)
        self.db.flush()
        return rp

    def _ensure_cas_storage_object(self, sha256: str, size: int, content: bytes) -> str:
        """Store content in CAS abstraction if not already present."""
        stmt = select(StorageObject).where(StorageObject.content_sha256 == sha256)
        existing = self.db.execute(stmt).scalars().first()
        if existing:
            existing.reference_count += 1
            if existing.state != "AVAILABLE":
                existing.state = "AVAILABLE"
            return existing.object_id

        obj_id = f"cas-{sha256[:16]}"
        sto = StorageObject(
            object_id=obj_id,
            content_sha256=sha256,
            stored_sha256=sha256,
            original_size=size,
            stored_size=size,
            compression_algorithm="NONE",
            compression_ratio=1.0,
            encryption_status="NONE",
            storage_path=f"objects/{sha256[:2]}/{sha256[2:4]}/{sha256}",
            reference_count=1,
            state="AVAILABLE",
            integrity_status="VALID"
        )
        self.db.add(sto)
        self.db.flush()
        return obj_id

    def _update_backup_chain(self, workload: Workload, rp: RecoveryPoint, backup_type: str, now: datetime.datetime) -> BackupChain:
        """Update or create backup chain continuity metadata."""
        stmt = select(BackupChain).where(BackupChain.workload_id == workload.workload_id)
        chain = self.db.execute(stmt).scalars().first()

        if not chain or backup_type.upper() == "FULL":
            chain_id = f"chain-{uuid.uuid4().hex[:12]}"
            chain = BackupChain(
                chain_id=chain_id,
                workload_id=workload.workload_id,
                base_recovery_point_id=str(rp.id),
                latest_recovery_point_id=str(rp.id),
                chain_length=1,
                status="VALID",
                last_validated_at=now,
                metadata_json=json.dumps({"chain_type": backup_type})
            )
            self.db.add(chain)
        else:
            chain.latest_recovery_point_id = str(rp.id)
            chain.chain_length += 1
            chain.last_validated_at = now

        self.db.flush()
        return chain

    def _record_telemetry(self, workload: Workload, metric_name: str, value: float):
        try:
            sample = MetricSample(
                metric_name=metric_name,
                value=value,
                source=f"workload:{workload.workload_id}",
                labels_json=json.dumps({"type": workload.type, "client_id": workload.client_id}),
                granularity="RAW"
            )
            self.db.add(sample)
        except Exception:
            pass

    def _record_compliance(self, workload: Workload, rp: RecoveryPoint, acr: ApplicationConsistencyRecord):
        try:
            evidence = ComplianceEvidence(
                domain="APPLICATION_CONSISTENCY",
                control_id="AC-BACKUP-01",
                resource_type="workload",
                resource_id=workload.workload_id,
                status="COMPLIANT" if acr.consistency_state in [APPLICATION_CONSISTENT, FILE_SYSTEM_CONSISTENT] else "NON_COMPLIANT",
                evidence_json=json.dumps({
                    "recovery_point_id": rp.id,
                    "consistency_state": acr.consistency_state,
                    "verification_method": acr.verification_method
                })
            )
            self.db.add(evidence)
        except Exception:
            pass
