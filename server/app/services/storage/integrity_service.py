"""Storage Integrity & Metrics Service for RetroVault V5 Storage Engine.

Performs checksum scrubbing, bit-rot detection, automated quarantine,
and repository-wide storage accounting metrics.
"""

import datetime
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.models.storage_object import StorageObject
from app.models.backup_file import BackupFile
from app.services.repository.local import get_repository
from app.services.compression import verify_stored_integrity


class StorageIntegrityService:
    """Provides bit-rot verification, quarantine, and storage efficiency metrics."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = get_repository()

    def scrub_storage_objects(
        self,
        batch_size: int = 100,
        verify_content: bool = True,
        object_id: Optional[str] = None,
    ) -> Dict[str, any]:
        """
        Verify physical storage objects against stored and content SHA-256 checksums.
        Corrupted objects are quarantined immediately to prevent silent propagation.
        """
        query = select(StorageObject).where(StorageObject.state == "AVAILABLE")
        if object_id:
            query = query.where(StorageObject.object_id == object_id)
        query = query.limit(batch_size)

        objects = self.db.execute(query).scalars().all()
        now = datetime.datetime.now(datetime.timezone.utc)

        checked = 0
        valid = 0
        corrupted = 0
        corrupted_details = []

        for obj in objects:
            checked += 1
            full_path = self.repo.resolve_stored_path(obj.storage_path)

            is_valid, reason = verify_stored_integrity(
                source_path=full_path,
                algorithm=obj.compression_algorithm,
                expected_stored_sha256=obj.stored_sha256,
                expected_content_sha256=obj.content_sha256 if verify_content else None,
            )

            if is_valid:
                obj.integrity_status = "VALID"
                obj.verified_at = now
                valid += 1
            else:
                obj.integrity_status = "CORRUPTED"
                obj.state = "CORRUPTED"
                obj.verified_at = now
                corrupted += 1
                quarantine_path = self.repo.quarantine_object(obj.storage_path, reason=reason)
                corrupted_details.append({
                    "object_id": obj.object_id,
                    "content_sha256": obj.content_sha256,
                    "storage_path": obj.storage_path,
                    "quarantine_path": quarantine_path,
                    "error": reason,
                })

        self.db.commit()
        return {
            "objects_checked": checked,
            "objects_valid": valid,
            "objects_corrupted": corrupted,
            "corrupted_items": corrupted_details,
            "timestamp": now.isoformat(),
        }

    def get_storage_metrics(self) -> Dict[str, any]:
        """
        Calculate global repository storage efficiency, deduplication, and compression metrics.
        """
        # 1. Total logical bytes backed up across all files
        total_logical_bytes = self.db.execute(
            select(func.coalesce(func.sum(BackupFile.size_bytes), 0))
        ).scalar_one()

        # 2. Total physical stored bytes for active objects
        total_stored_bytes = self.db.execute(
            select(func.coalesce(func.sum(StorageObject.stored_size), 0)).where(
                StorageObject.state == "AVAILABLE"
            )
        ).scalar_one()

        # 3. Total original bytes for unique active objects (to isolate compression ratio from dedup ratio)
        unique_original_bytes = self.db.execute(
            select(func.coalesce(func.sum(StorageObject.original_size), 0)).where(
                StorageObject.state == "AVAILABLE"
            )
        ).scalar_one()

        # 4. Total object counts
        total_objects = self.db.execute(
            select(func.count(StorageObject.id)).where(StorageObject.state == "AVAILABLE")
        ).scalar_one()

        total_files = self.db.execute(
            select(func.count(BackupFile.id))
        ).scalar_one()

        # Ratios
        dedup_ratio = round(total_logical_bytes / unique_original_bytes, 2) if unique_original_bytes > 0 else 1.0
        compression_ratio = round(unique_original_bytes / total_stored_bytes, 2) if total_stored_bytes > 0 else 1.0
        overall_ratio = round(total_logical_bytes / total_stored_bytes, 2) if total_stored_bytes > 0 else 1.0
        bytes_saved = max(0, total_logical_bytes - total_stored_bytes)
        savings_percent = round((bytes_saved / total_logical_bytes) * 100.0, 1) if total_logical_bytes > 0 else 0.0

        repo_health = self.repo.validate_storage_health()

        return {
            "total_logical_bytes": total_logical_bytes,
            "total_stored_bytes": total_stored_bytes,
            "unique_original_bytes": unique_original_bytes,
            "bytes_saved": bytes_saved,
            "savings_percent": savings_percent,
            "deduplication_ratio": dedup_ratio,
            "compression_ratio": compression_ratio,
            "overall_efficiency_ratio": overall_ratio,
            "total_files_referenced": total_files,
            "unique_storage_objects": total_objects,
            "repository_health": repo_health,
        }
