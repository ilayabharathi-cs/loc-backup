"""Background Hydrator for Instant Virtual Recovery."""

import os
import time
import datetime
import logging
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.models.virtual_recovery_v12_models import VirtualRecoverySession, VirtualRecoveryHydrationItem
from app.services.v12.virtual_recovery.read_engine import ReadOnDemandEngine

logger = logging.getLogger(__name__)


class BackgroundHydrator:
    """
    Gradually restores complete dataset into target path in the background.
    Resumable, tracks speed and ETA, and terminates cleanly when full dataset is hydrated.
    """

    def __init__(self, db: Session, read_engine: Optional[ReadOnDemandEngine] = None):
        self.db = db
        self.read_engine = read_engine or ReadOnDemandEngine(db)

    def hydrate_batch(
        self,
        session: VirtualRecoverySession,
        max_files: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Processes a batch of pending hydration items for the session.
        Writes actual physical data bytes to target_path, ensuring resumability.
        """
        if session.state in ["CANCELLED", "COMPLETED", "FAILED", "UNMOUNTING"]:
            return {
                "session_id": session.session_id,
                "status": session.hydration_status,
                "hydrated_count": 0,
                "message": f"Hydration not applicable in state {session.state}"
            }

        start_perf = time.perf_counter()

        # Query pending hydration items
        query = (
            select(VirtualRecoveryHydrationItem)
            .where(
                VirtualRecoveryHydrationItem.session_id == session.id,
                VirtualRecoveryHydrationItem.status.in_(["PENDING", "FAILED"])
            )
            .order_by(VirtualRecoveryHydrationItem.id.asc())
        )
        if max_files:
            query = query.limit(max_files)

        items = self.db.scalars(query).all()

        if not items:
            # Check if all items are hydrated
            remaining = self.db.scalar(
                select(func.count(VirtualRecoveryHydrationItem.id)).where(
                    VirtualRecoveryHydrationItem.session_id == session.id,
                    VirtualRecoveryHydrationItem.status != "HYDRATED"
                )
            )
            if remaining == 0 and session.total_files > 0:
                self._mark_session_hydrated(session)
            return {
                "session_id": session.session_id,
                "status": session.hydration_status,
                "hydrated_count": 0,
                "remaining": remaining or 0,
                "message": "All items already hydrated"
            }

        # Set session state to HYDRATING if currently READY
        if session.state == "READY":
            session.state = "HYDRATING"
            session.hydration_status = "RUNNING"
            if not session.hydration_started_at:
                session.hydration_started_at = datetime.datetime.now(datetime.timezone.utc)
            self.db.commit()

        hydrated_this_batch = 0
        bytes_this_batch = 0

        target_base = os.path.abspath(session.target_path)
        os.makedirs(target_base, exist_ok=True)

        for item in items:
            if session.hydration_status == "PAUSED":
                logger.info(f"Hydration paused for session '{session.session_id}'")
                break

            item_rel = item.relative_path.replace("\\", "/").lstrip("/")
            out_path = os.path.normpath(os.path.join(target_base, item_rel))

            # Prevent directory traversal
            if not out_path.startswith(target_base):
                item.status = "FAILED"
                item.error_message = f"Path traversal rejected: '{item_rel}'"
                self.db.commit()
                continue

            try:
                # Fetch data via on-demand read engine
                data = self.read_engine.read_logical_path(session, item_rel)

                # Write physical file atomically
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                tmp_out = f"{out_path}.part"
                with open(tmp_out, "wb") as f:
                    f.write(data)
                os.replace(tmp_out, out_path)

                item.status = "HYDRATED"
                item.hydrated_at = datetime.datetime.now(datetime.timezone.utc)
                item.size_bytes = len(data)

                hydrated_this_batch += 1
                bytes_this_batch += len(data)
                session.hydrated_files += 1
                session.hydrated_bytes += len(data)

                self.db.commit()
            except Exception as e:
                logger.warning(f"Failed hydrating item '{item_rel}': {e}")
                item.status = "FAILED"
                item.error_message = str(e)
                self.db.commit()

        # Update speed & ETA metrics
        duration = max(time.perf_counter() - start_perf, 0.001)
        speed = bytes_this_batch / duration
        session.hydration_speed_bps = round(speed, 2)

        remaining_bytes = max(session.total_bytes - session.hydrated_bytes, 0)
        session.hydration_eta_seconds = round(remaining_bytes / speed, 1) if speed > 0 else 0.0

        # Check completion
        remaining_items = self.db.scalar(
            select(func.count(VirtualRecoveryHydrationItem.id)).where(
                VirtualRecoveryHydrationItem.session_id == session.id,
                VirtualRecoveryHydrationItem.status != "HYDRATED"
            )
        )
        if remaining_items == 0:
            self._mark_session_hydrated(session)

        self.db.commit()

        return {
            "session_id": session.session_id,
            "status": session.hydration_status,
            "hydrated_count": hydrated_this_batch,
            "bytes_hydrated": bytes_this_batch,
            "total_hydrated_bytes": session.hydrated_bytes,
            "remaining_bytes": remaining_bytes,
            "speed_bps": session.hydration_speed_bps,
            "eta_seconds": session.hydration_eta_seconds,
            "remaining_items": remaining_items or 0
        }

    def _mark_session_hydrated(self, session: VirtualRecoverySession) -> None:
        """
        Marks background hydration completely finished and computes RTO metric.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        session.state = "COMPLETING"
        session.hydration_status = "COMPLETED"
        session.completed_at = now

        base_time = session.mounted_at or session.created_at
        if base_time:
            if base_time.tzinfo is None:
                delta = (now.replace(tzinfo=None) - base_time).total_seconds()
            else:
                delta = (now - base_time).total_seconds()
            session.time_to_full_hydration_ms = round(max(delta, 0.0) * 1000.0, 2)

        session.state = "COMPLETED"
        logger.info(
            f"virtual_recovery_hydration_completed: session='{session.session_id}', "
            f"total_bytes={session.hydrated_bytes}, time_to_full_hydration={session.time_to_full_hydration_ms}ms"
        )
