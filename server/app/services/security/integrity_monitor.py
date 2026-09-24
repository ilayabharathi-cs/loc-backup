"""Continuous Backup Integrity Monitor for RetroVault V8.

Performs deep cryptographic verification of physical CAS objects and backup repositories.
Detects tampering, missing blocks, bit rot, and isolates corrupted objects with quarantine tagging.
"""

import datetime
import hashlib
import json
import logging
import os
import uuid
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.storage_object import StorageObject
from app.models.storage_repository import StorageRepository
from app.models.security_v8_models import IntegrityScan, SecurityEvent
from app.services.repository.local import get_repository

logger = logging.getLogger(__name__)


class IntegrityMonitor:
    """Verifies stored objects against recorded SHA-256 hashes and isolates corruptions."""

    def __init__(self, db: Session, repository_id: Optional[int] = None):
        self.db = db
        self.repository_id = repository_id
        self.repo_service = get_repository()

    def run_integrity_scan(
        self,
        repository_id: int,
        scan_type: str = "FULL",  # FULL or SAMPLE
        sample_limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """Scans repository objects, verifies SHA-256 integrity, and quarantines corrupted items."""
        repo = self.db.query(StorageRepository).filter(StorageRepository.id == repository_id).first()
        if not repo:
            return {"error": f"Repository {repository_id} not found", "status": "FAILED"}

        scan_uuid = f"SCAN-{uuid.uuid4().hex[:12].upper()}"
        start_time = datetime.datetime.now(datetime.timezone.utc)

        scan_record = IntegrityScan(
            scan_id=scan_uuid,
            repository_id=repository_id,
            scan_type=scan_type,
            total_objects=0,
            valid_objects=0,
            corrupted_objects=0,
            missing_objects=0,
            duration_seconds=0.0,
            status="RUNNING"
        )
        self.db.add(scan_record)
        self.db.commit()

        # Query storage objects
        query = self.db.query(StorageObject).filter(StorageObject.state != "DELETED")
        if scan_type == "SAMPLE" and sample_limit:
            query = query.limit(sample_limit)
        objects = query.all()

        total = len(objects)
        valid_count = 0
        corrupt_count = 0
        missing_count = 0
        corrupted_details = []

        repo_root = repo.effective_root_path if hasattr(repo, "effective_root_path") else (repo.root_path or repo.path)
        for obj in objects:
            if os.path.isabs(obj.storage_path):
                full_path = obj.storage_path
            elif repo_root:
                full_path = os.path.join(repo_root, obj.storage_path)
            else:
                full_path = self.repo_service.resolve_stored_path(obj.storage_path)

            if not os.path.isfile(full_path):
                missing_count += 1
                obj.state = "CORRUPTED"
                obj.integrity_status = "CORRUPTED"
                obj.quarantined_at = datetime.datetime.now(datetime.timezone.utc)
                obj.quarantine_reason = "Physical file missing on disk"
                corrupted_details.append({
                    "object_id": obj.object_id,
                    "error": "File missing on disk",
                    "path": obj.storage_path
                })
                continue

            # Verify cryptographic SHA-256
            hasher = hashlib.sha256()
            try:
                with open(full_path, "rb") as f:
                    while chunk := f.read(65536):
                        hasher.update(chunk)
                computed_sha = hasher.hexdigest().lower()

                if computed_sha != obj.stored_sha256.lower():
                    corrupt_count += 1
                    obj.state = "CORRUPTED"
                    obj.integrity_status = "CORRUPTED"
                    obj.quarantined_at = datetime.datetime.now(datetime.timezone.utc)
                    obj.quarantine_reason = f"Hash mismatch: expected {obj.stored_sha256}, got {computed_sha}"

                    # Physically quarantine file
                    try:
                        self.repo_service.quarantine_corrupted_object(full_path, "sha256_mismatch")
                    except Exception as q_err:
                        logger.error(f"Failed to move corrupted object {obj.object_id} to quarantine: {q_err}")

                    corrupted_details.append({
                        "object_id": obj.object_id,
                        "expected_sha": obj.stored_sha256,
                        "actual_sha": computed_sha,
                        "path": obj.storage_path
                    })
                else:
                    valid_count += 1
                    obj.integrity_status = "VALID"
                    obj.verified_at = datetime.datetime.now(datetime.timezone.utc)
            except Exception as e:
                corrupt_count += 1
                obj.state = "CORRUPTED"
                obj.integrity_status = "CORRUPTED"
                obj.quarantined_at = datetime.datetime.now(datetime.timezone.utc)
                obj.quarantine_reason = f"Read error: {str(e)}"
                corrupted_details.append({
                    "object_id": obj.object_id,
                    "error": str(e),
                    "path": obj.storage_path
                })

        duration = (datetime.datetime.now(datetime.timezone.utc) - start_time).total_seconds()

        # Update scan record
        scan_record.total_objects = total
        scan_record.valid_objects = valid_count
        scan_record.corrupted_objects = corrupt_count
        scan_record.missing_objects = missing_count
        scan_record.duration_seconds = round(duration, 2)
        scan_record.status = "COMPLETED" if (corrupt_count == 0 and missing_count == 0) else "ANOMALY_DETECTED"
        scan_record.details_json = json.dumps({
            "corrupted_details": corrupted_details[:50],
            "total_corrupted": corrupt_count + missing_count
        })

        # If corruptions/missing blocks detected, emit SecurityEvent
        if corrupt_count > 0 or missing_count > 0:
            sec_event = SecurityEvent(
                event_type="INTEGRITY_FAILURE",
                severity="CRITICAL",
                repository_id=repository_id,
                score=90,
                description=f"Integrity monitor detected {corrupt_count} corrupted and {missing_count} missing storage objects.",
                evidence_json=json.dumps({"scan_id": scan_uuid, "corrupted_details": corrupted_details[:20]}),
                status="OPEN"
            )
            self.db.add(sec_event)

        self.db.commit()

        return {
            "scan_id": scan_uuid,
            "repository_id": repository_id,
            "scan_type": scan_type,
            "total_objects": total,
            "valid_objects": valid_count,
            "corrupted_objects": corrupt_count,
            "missing_objects": missing_count,
            "duration_seconds": round(duration, 2),
            "status": scan_record.status,
            "corrupted_details": corrupted_details,
        }
