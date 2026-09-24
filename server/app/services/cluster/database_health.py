"""Database health provider and connection resiliency abstraction for RetroVault V9."""

import time
import logging
from typing import Dict, Any, Callable, TypeVar
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)

T = TypeVar("T")


class DatabaseHealthProvider:
    """Monitors database connectivity, query latency, dialect, and implements retry wrappers."""

    def __init__(self, db: Session):
        self.db = db

    def check_health(self) -> Dict[str, Any]:
        """Performs a live probe against the configured database engine."""
        start_time = time.perf_counter()
        try:
            # Universal live ping
            result = self.db.execute(text("SELECT 1")).scalar()
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

            # Detect dialect
            bind = self.db.get_bind()
            dialect_name = bind.dialect.name if bind else "unknown"

            # Determine pool status if available
            pool_info = {}
            if hasattr(bind, "pool") and bind.pool:
                pool = bind.pool
                def _safe_val(obj, attr):
                    val = getattr(obj, attr, 0)
                    if callable(val):
                        try:
                            return val()
                        except Exception:
                            return 0
                    return val if isinstance(val, (int, float, str)) else 0

                pool_info = {
                    "pool_size": _safe_val(pool, "size"),
                    "checked_in": _safe_val(pool, "checkedin"),
                    "checked_out": _safe_val(pool, "checkedout"),
                    "overflow": _safe_val(pool, "overflow"),
                }

            is_healthy = result == 1
            status = "HEALTHY" if latency_ms < 100 else "DEGRADED"

            return {
                "status": status,
                "is_connected": is_healthy,
                "latency_ms": latency_ms,
                "dialect": dialect_name,
                "pool": pool_info,
                "ha_mode": "POSTGRESQL_DISTRIBUTED" if dialect_name == "postgresql" else "LOCAL_EMBEDDED"
            }
        except Exception as e:
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "OFFLINE",
                "is_connected": False,
                "latency_ms": latency_ms,
                "error": str(e),
                "dialect": "unknown",
                "ha_mode": "DISCONNECTED"
            }

    @staticmethod
    def execute_with_retry(
        func: Callable[[], T],
        max_retries: int = 3,
        initial_backoff_seconds: float = 0.5,
        backoff_multiplier: float = 2.0
    ) -> T:
        """Executes a database callable with exponential backoff on transient connection failures."""
        attempt = 0
        backoff = initial_backoff_seconds
        last_exception = None

        while attempt < max_retries:
            try:
                return func()
            except Exception as ex:
                attempt += 1
                last_exception = ex
                if attempt >= max_retries:
                    logger.error(f"Operation failed after {attempt} retries: {ex}")
                    raise ex
                logger.warning(f"Database operation failed (attempt {attempt}/{max_retries}), retrying in {backoff:.2f}s: {ex}")
                time.sleep(backoff)
                backoff *= backoff_multiplier

        raise last_exception or RuntimeError("Database operation failed")
