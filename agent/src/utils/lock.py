"""Local backup process mutual exclusion lock for RetroVault Agent V4."""

import os
import sys
from typing import Optional
from agent.src.utils.windows import get_programdata_path
from agent.src.logger import get_logger


class BackupConcurrencyError(RuntimeError):
    """Raised when an attempt is made to run concurrent backups locally."""
    pass


class BackupLock:
    """
    Ensures only one backup operation runs at a time within the agent.
    Avoids race conditions between scheduler, manual triggers, and recovery workers.
    """

    def __init__(self, lock_name: str = "retrovault_backup.lock", custom_dir: Optional[str] = None):
        self.lock_name = lock_name
        self.logger = get_logger()
        if custom_dir:
            lock_dir = custom_dir
        else:
            prog_data = get_programdata_path()
            lock_dir = os.path.join(prog_data, "RetroVault", "agent", "locks")

        try:
            os.makedirs(lock_dir, exist_ok=True)
        except Exception:
            lock_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "locks"))
            os.makedirs(lock_dir, exist_ok=True)

        self.lock_file_path = os.path.join(lock_dir, lock_name)
        self._lock_file = None
        self._is_locked = False

    @property
    def is_locked(self) -> bool:
        return self._is_locked

    def acquire(self) -> bool:
        """Acquire lock exclusively. Raises BackupConcurrencyError if already held."""
        if self._is_locked:
            return True

        try:
            if sys.platform == "win32":
                import msvcrt
                self._lock_file = open(self.lock_file_path, "wb")
                msvcrt.locking(self._lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                self._lock_file = open(self.lock_file_path, "wb")
                fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

            self._is_locked = True
            self.logger.debug(f"Acquired local backup lock: '{self.lock_file_path}'")
            return True
        except (IOError, OSError) as e:
            if self._lock_file:
                try:
                    self._lock_file.close()
                except Exception:
                    pass
                self._lock_file = None
            msg = f"Another backup process is already running locally (lock: '{self.lock_file_path}'): {e}"
            self.logger.warning(msg)
            raise BackupConcurrencyError(msg)

    def release(self) -> None:
        """Release the acquired lock safely."""
        if not self._is_locked:
            return

        try:
            if self._lock_file:
                if sys.platform == "win32":
                    import msvcrt
                    try:
                        msvcrt.locking(self._lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                    except Exception:
                        pass
                else:
                    import fcntl
                    try:
                        fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
                    except Exception:
                        pass

                self._lock_file.close()
                self._lock_file = None

            if os.path.exists(self.lock_file_path):
                try:
                    os.remove(self.lock_file_path)
                except OSError:
                    pass

            self._is_locked = False
            self.logger.debug(f"Released local backup lock: '{self.lock_file_path}'")
        except Exception as e:
            self.logger.warning(f"Error releasing local backup lock: {e}")

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
