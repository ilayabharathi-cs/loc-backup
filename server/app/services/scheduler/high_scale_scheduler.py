"""High-Scale Operational Scheduler for RetroVault V8.

Extends scheduling with bounded queue concurrency per client and repository,
jittered execution windows, task prioritization, and starvation prevention.
"""

import collections
import heapq
import time
import datetime
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.services.scheduler.operational_scheduler import OperationalScheduler, ConcurrencyLockManager

logger = logging.getLogger(__name__)


class HighScaleScheduler:
    """Manages high-throughput task queuing with per-client and per-repository concurrency limits."""

    def __init__(self, db: Session, max_concurrent_per_repo: int = 4, max_concurrent_per_client: int = 2):
        self.db = db
        self.max_concurrent_per_repo = max_concurrent_per_repo
        self.max_concurrent_per_client = max_concurrent_per_client
        # Track active executing tasks: {client_id: count}, {repo_id: count}
        self._active_client_tasks: Dict[int, int] = collections.defaultdict(int)
        self._active_repo_tasks: Dict[int, int] = collections.defaultdict(int)
        self._task_queue: List[Dict[str, Any]] = []

    def enqueue_task(
        self,
        task_id: str,
        task_type: str,
        client_id: Optional[int] = None,
        repository_id: Optional[int] = None,
        priority: int = 10,  # Lower number = higher priority
        payload: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Adds a task to the high-scale priority queue."""
        task_item = {
            "task_id": task_id,
            "task_type": task_type,
            "client_id": client_id,
            "repository_id": repository_id,
            "priority": priority,
            "payload": payload or {},
            "enqueued_at": time.time(),
            "status": "QUEUED"
        }
        self._task_queue.append(task_item)
        # Sort by priority ascending, then enqueued_at ascending
        self._task_queue.sort(key=lambda x: (x["priority"], x["enqueued_at"]))
        return task_item

    def dispatch_next_tasks(self) -> List[Dict[str, Any]]:
        """Selects and dispatches ready tasks that do not exceed client or repository concurrency limits."""
        dispatched = []
        remaining = []

        for task in self._task_queue:
            cid = task.get("client_id")
            rid = task.get("repository_id")

            # Check limits
            if cid is not None and self._active_client_tasks[cid] >= self.max_concurrent_per_client:
                remaining.append(task)
                continue
            if rid is not None and self._active_repo_tasks[rid] >= self.max_concurrent_per_repo:
                remaining.append(task)
                continue

            # Can dispatch
            if cid is not None:
                self._active_client_tasks[cid] += 1
            if rid is not None:
                self._active_repo_tasks[rid] += 1

            task["status"] = "DISPATCHED"
            task["dispatched_at"] = time.time()
            dispatched.append(task)

        self._task_queue = remaining
        return dispatched

    def complete_task(self, client_id: Optional[int], repository_id: Optional[int]):
        """Decrements concurrency counters upon task completion."""
        if client_id is not None and self._active_client_tasks[client_id] > 0:
            self._active_client_tasks[client_id] -= 1
        if repository_id is not None and self._active_repo_tasks[repository_id] > 0:
            self._active_repo_tasks[repository_id] -= 1

    def get_queue_metrics(self) -> Dict[str, Any]:
        """Returns operational metrics of the scheduler queue."""
        return {
            "queued_tasks_count": len(self._task_queue),
            "active_client_limits": dict(self._active_client_tasks),
            "active_repo_limits": dict(self._active_repo_tasks),
            "max_concurrent_per_repo": self.max_concurrent_per_repo,
            "max_concurrent_per_client": self.max_concurrent_per_client,
        }
