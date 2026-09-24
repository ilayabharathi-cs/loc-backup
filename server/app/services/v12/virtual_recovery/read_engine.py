"""Read-on-Demand Engine for Instant Virtual Recovery."""

import os
import time
import hashlib
import datetime
import logging
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.virtual_recovery_v12_models import VirtualRecoverySession
from app.models.recovery_point import RecoveryPoint
from app.models.backup_file import BackupFile
from app.models.storage_object import StorageObject
from app.models.storage_tier_v12_models import StorageTier, CloudOffloadedObject
from app.services.restore.planner import RestorePlanner
from app.services.v12.virtual_recovery.cache import get_ivr_cache, BoundedLruCache
from app.services.v12.virtual_recovery.provider_base import (
    ObjectUnavailableError,
    IntegrityVerificationError
)
from app.services.v12.cloud.tiering_manager import TieringManager
from app.config import settings

logger = logging.getLogger(__name__)


class ReadOnDemandEngine:
    """
    Executes lazy, on-demand block and object retrieval for Virtual Recovery targets.
    Enforces local-first data resolution: Cache -> Local CAS -> Cloud Tier.
    Strictly guarantees cryptographic checksum verification on every read.
    """

    def __init__(
        self,
        db: Session,
        cache: Optional[BoundedLruCache] = None,
        tiering_manager: Optional[TieringManager] = None
    ):
        self.db = db
        self.cache = cache or get_ivr_cache()
        self.tiering_manager = tiering_manager or TieringManager(db)

    def read_logical_path(
        self,
        session: VirtualRecoverySession,
        logical_path: str,
        offset: int = 0,
        length: Optional[int] = None
    ) -> bytes:
        """
        Reads data for a logical file within a Virtual Recovery Session.
        Performs manifest lookup, cache check, local CAS fetch, cloud fallback, and integrity verification.
        """
        start_time = time.perf_counter()

        # Normalize relative path
        norm_path = logical_path.replace("\\", "/").lstrip("/")

        # Step 1: Check in-memory bounded LRU cache
        cached_bytes = self.cache.get(session.session_id, norm_path)
        source = "CACHE"

        if cached_bytes is None:
            # Cache miss: resolve logical manifest entry
            bf, so = self._resolve_manifest_entry(session.recovery_point_id, norm_path)

            expected_sha = bf.sha256 or (so.stored_sha256 if so else None)
            if not expected_sha:
                raise ObjectUnavailableError(f"Missing checksum metadata for logical path '{norm_path}'")

            # Step 2: Local CAS lookup
            raw_bytes, source = self._fetch_from_local_or_cloud(so, session.cloud_tier_id, expected_sha)

            # Step 3: Strict Cryptographic Verification
            actual_sha = hashlib.sha256(raw_bytes).hexdigest()
            if actual_sha.lower() != expected_sha.lower():
                logger.error(f"Checksum mismatch for '{norm_path}': expected {expected_sha}, got {actual_sha}")
                raise IntegrityVerificationError(
                    f"Integrity check failed for '{norm_path}': expected {expected_sha}, got {actual_sha}"
                )

            # Step 4: Populate LRU Cache
            self.cache.put(session.session_id, norm_path, raw_bytes, expected_sha)
            cached_bytes = raw_bytes

        # Apply slicing (offset and length)
        total_len = len(cached_bytes)
        if offset < 0 or offset > total_len:
            raise ValueError(f"Offset {offset} out of bounds for object size {total_len}")

        end = total_len if length is None else min(offset + length, total_len)
        result_bytes = cached_bytes[offset:end]

        # Step 5: Telemetry & Metrics Update
        self._record_read_telemetry(session, len(result_bytes), source, start_time)

        return result_bytes

    def _resolve_manifest_entry(self, recovery_point_id: int, relative_path: str) -> Tuple[BackupFile, Optional[StorageObject]]:
        """
        Traverses recovery point logical manifest to locate target BackupFile and underlying StorageObject.
        """
        logical_files = RestorePlanner.get_recovery_point_logical_files(self.db, recovery_point_id)
        target_bf = None
        for f in logical_files:
            rel = (f.relative_path or os.path.basename(f.original_path)).replace("\\", "/").lstrip("/")
            if rel.lower() == relative_path.lower():
                target_bf = f
                break

        if not target_bf:
            raise ObjectUnavailableError(f"Logical path '{relative_path}' not found in Recovery Point {recovery_point_id}")

        so = None
        if target_bf.storage_object_id:
            so = self.db.scalar(select(StorageObject).where(StorageObject.id == target_bf.storage_object_id))

        return target_bf, so

    def _fetch_from_local_or_cloud(
        self,
        so: Optional[StorageObject],
        cloud_tier_id: Optional[int],
        expected_sha: str
    ) -> Tuple[bytes, str]:
        """
        Implements local-first data retrieval priority:
        1. Local CAS
        2. Configured Cloud Storage Tier
        3. Fail safely with ObjectUnavailableError
        """
        # Priority 1: Local CAS filesystem
        if so and so.storage_path:
            repo_root = settings.get_repository_root()
            candidate_paths = [
                so.storage_path,
                os.path.join(repo_root, so.storage_path.lstrip("/\\")),
                os.path.join(repo_root, "objects", so.storage_path.lstrip("/\\"))
            ]
            for p in candidate_paths:
                if os.path.exists(p) and os.path.isfile(p):
                    try:
                        with open(p, "rb") as f:
                            data = f.read()
                            return data, "LOCAL_CAS"
                    except OSError as e:
                        logger.warning(f"Failed reading local CAS file '{p}': {e}")

            # Check synthetic test bytes if attached
            if hasattr(so, "_synthetic_bytes") and so._synthetic_bytes:
                return so._synthetic_bytes, "LOCAL_CAS"

        # Priority 2: Cloud Storage Tier fallback
        if cloud_tier_id and so:
            tier = self.db.scalar(select(StorageTier).where(StorageTier.id == cloud_tier_id))
            if tier and tier.is_enabled and tier.state in ["READY", "CREATED"]:
                try:
                    logger.info(f"Local CAS missing for '{so.object_id}'; fetching from cloud tier '{tier.name}'")
                    cloud_bytes = self.tiering_manager.restore_from_tier(so.object_id, tier.id)
                    return cloud_bytes, "CLOUD_TIER"
                except Exception as e:
                    logger.warning(f"Cloud tier fetch failed for '{so.object_id}': {e}")

        # Priority 3: Fail with explicit error
        obj_ref = so.object_id if so else expected_sha
        raise ObjectUnavailableError(
            f"Object '{obj_ref}' is unavailable in local CAS and no functional cloud storage tier could provide it"
        )

    def _record_read_telemetry(
        self,
        session: VirtualRecoverySession,
        bytes_served: int,
        source: str,
        start_perf: float
    ) -> None:
        """
        Tracks read counts, bytes, cache hit/miss ratio, and first-access latency.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        session.read_requests_count += 1
        session.bytes_read += bytes_served

        # RTO First-Access Metric
        if session.first_access_at is None:
            session.first_access_at = now
            base_time = session.mounted_at or session.created_at
            if base_time:
                # If tzinfo mismatch, convert to naive UTC or tz-aware
                if base_time.tzinfo is None:
                    delta = (now.replace(tzinfo=None) - base_time).total_seconds()
                else:
                    delta = (now - base_time).total_seconds()
                session.time_to_first_access_ms = round(max(delta, 0.0) * 1000.0, 2)
                logger.info(
                    f"virtual_recovery_first_access: session='{session.session_id}', "
                    f"time_to_first_access={session.time_to_first_access_ms}ms"
                )

        # Update cache metrics from LRU engine
        cache_stats = self.cache.get_stats()
        session.cache_hits = cache_stats["hits"]
        session.cache_misses = cache_stats["misses"]
        session.cache_bytes = cache_stats["current_bytes"]

        self.db.commit()
