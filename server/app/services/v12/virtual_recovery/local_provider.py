"""Local Filesystem Implementation of Virtual Recovery Provider."""

import os
import time
import datetime
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.virtual_recovery_v12_models import VirtualRecoverySession, VirtualRecoveryHydrationItem
from app.services.v12.virtual_recovery.provider_base import (
    VirtualRecoveryProviderBase,
    MountError,
    UnmountError
)
from app.services.v12.virtual_recovery.read_engine import ReadOnDemandEngine
from app.services.v12.virtual_recovery.hydrator import BackgroundHydrator
from app.services.v12.virtual_recovery.cache import get_ivr_cache

logger = logging.getLogger(__name__)


class LocalVirtualRecoveryProvider(VirtualRecoveryProviderBase):
    """
    Local filesystem virtual recovery provider.
    Instantly stubs directory structures and provides on-demand lazy read fetching.
    """

    def __init__(
        self,
        db: Session,
        cache: Optional[BoundedLruCache] = None,
        read_engine: Optional[ReadOnDemandEngine] = None,
        tiering_manager: Optional[Any] = None
    ):
        self.db = db
        self.cache = cache or get_ivr_cache()
        self.tiering_manager = tiering_manager
        self.read_engine = read_engine or ReadOnDemandEngine(db, cache=self.cache, tiering_manager=tiering_manager)
        self.hydrator = BackgroundHydrator(db, read_engine=self.read_engine)

    def prepare(self, session: VirtualRecoverySession, manifest: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Initializes hydration tracking items for all files in the logical manifest.
        """
        total_bytes = 0
        total_files = len(manifest)

        # Clear any existing hydration items if re-preparing
        existing_items = self.db.scalars(
            select(VirtualRecoveryHydrationItem).where(VirtualRecoveryHydrationItem.session_id == session.id)
        ).all()
        for item in existing_items:
            self.db.delete(item)

        for entry in manifest:
            rel_path = entry.get("relative_path") or os.path.basename(entry.get("original_path", "unknown"))
            size = entry.get("size_bytes", 0)
            sha = entry.get("sha256", "")
            so_id = entry.get("storage_object_id")
            total_bytes += size

            h_item = VirtualRecoveryHydrationItem(
                session_id=session.id,
                relative_path=rel_path.replace("\\", "/").lstrip("/"),
                storage_object_id=str(so_id) if so_id else None,
                size_bytes=size,
                sha256=sha,
                status="PENDING"
            )
            self.db.add(h_item)

        session.total_files = total_files
        session.total_bytes = total_bytes
        session.prepared_at = datetime.datetime.now(datetime.timezone.utc)
        self.db.commit()

        logger.info(f"virtual_recovery_prepared: session='{session.session_id}', files={total_files}, bytes={total_bytes}")
        return {
            "session_id": session.session_id,
            "status": "PREPARED",
            "total_files": total_files,
            "total_bytes": total_bytes
        }

    def mount(self, session: VirtualRecoverySession, target_path: str) -> Dict[str, Any]:
        """
        Creates directory hierarchy and virtual file placeholders at target_path for immediate browsing.
        """
        norm_target = os.path.abspath(target_path)
        try:
            os.makedirs(norm_target, exist_ok=True)

            # Query all manifest items for the session
            items = self.db.scalars(
                select(VirtualRecoveryHydrationItem).where(VirtualRecoveryHydrationItem.session_id == session.id)
            ).all()

            for item in items:
                file_rel = item.relative_path.replace("\\", "/").lstrip("/")
                full_dest = os.path.normpath(os.path.join(norm_target, file_rel))

                if not full_dest.startswith(norm_target):
                    raise MountError(f"Directory traversal detected: '{file_rel}'")

                os.makedirs(os.path.dirname(full_dest), exist_ok=True)
                # Create empty virtual stub file if not already present
                if not os.path.exists(full_dest):
                    with open(full_dest, "wb") as f:
                        pass  # Stub placeholder for on-demand hydration

            now = datetime.datetime.now(datetime.timezone.utc)
            session.mount_point = norm_target
            session.mounted_at = now
            self.db.commit()

            logger.info(f"virtual_recovery_mounted: session='{session.session_id}', mount_point='{norm_target}'")
            return {
                "session_id": session.session_id,
                "mount_point": norm_target,
                "status": "MOUNTED",
                "mounted_at": now.isoformat()
            }
        except Exception as e:
            logger.error(f"Failed mounting session '{session.session_id}': {e}")
            raise MountError(f"Failed to mount virtual recovery session at '{target_path}': {str(e)}")

    def read(
        self,
        session: VirtualRecoverySession,
        logical_path: str,
        offset: int = 0,
        length: Optional[int] = None
    ) -> bytes:
        return self.read_engine.read_logical_path(session, logical_path, offset=offset, length=length)

    def prefetch(self, session: VirtualRecoverySession, paths: List[str]) -> Dict[str, Any]:
        """
        Prefetches requested paths into the LRU cache.
        """
        prefetched = []
        failed = []

        for p in paths:
            clean_path = p.replace("\\", "/").lstrip("/")
            try:
                data = self.read_engine.read_logical_path(session, clean_path)
                prefetched.append({"path": clean_path, "bytes": len(data)})
            except Exception as e:
                failed.append({"path": clean_path, "error": str(e)})

        logger.info(
            f"virtual_recovery_prefetch: session='{session.session_id}', "
            f"prefetched={len(prefetched)}, failed={len(failed)}"
        )
        return {
            "session_id": session.session_id,
            "prefetched_count": len(prefetched),
            "failed_count": len(failed),
            "prefetched": prefetched,
            "failed": failed
        }

    def hydrate(self, session: VirtualRecoverySession, max_files: Optional[int] = None) -> Dict[str, Any]:
        return self.hydrator.hydrate_batch(session, max_files=max_files)

    def validate(self, session: VirtualRecoverySession) -> Dict[str, Any]:
        """
        Validates responsiveness and accessibility of the virtual recovery mount.
        """
        if not session.mount_point or not os.path.exists(session.mount_point):
            return {
                "session_id": session.session_id,
                "valid": False,
                "error": "Mount point does not exist or is not attached"
            }

        start = time.perf_counter()
        # Test directory writability / readability
        test_file = os.path.join(session.mount_point, ".ivr_probe.tmp")
        try:
            with open(test_file, "w") as f:
                f.write("probe")
            os.remove(test_file)
            latency = (time.perf_counter() - start) * 1000.0
            return {
                "session_id": session.session_id,
                "valid": True,
                "mount_point": session.mount_point,
                "probe_latency_ms": round(latency, 2)
            }
        except Exception as e:
            return {
                "session_id": session.session_id,
                "valid": False,
                "error": f"Validation probe failed: {str(e)}"
            }

    def unmount(self, session: VirtualRecoverySession) -> bool:
        """
        Safely detaches virtual recovery mount and clears LRU cache for the session.
        """
        try:
            self.cache.invalidate_session(session.session_id)
            session.unmounted_at = datetime.datetime.now(datetime.timezone.utc)
            self.db.commit()
            logger.info(f"virtual_recovery_unmounted: session='{session.session_id}'")
            return True
        except Exception as e:
            logger.error(f"Failed unmounting session '{session.session_id}': {e}")
            raise UnmountError(f"Failed to unmount session: {str(e)}")

    def cleanup(self, session: VirtualRecoverySession) -> bool:
        """
        Releases session resources.
        """
        self.cache.invalidate_session(session.session_id)
        return True
