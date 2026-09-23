"""Production retry engine with exponential backoff and jitter for RetroVault V4."""

import time
import random
from typing import Callable, TypeVar, Optional, Tuple
from urllib.error import HTTPError, URLError
from agent.src.logger import get_logger

T = TypeVar("T")

RETRYABLE_HTTP_STATUSES = {408, 429, 500, 502, 503, 504}
NON_RETRYABLE_HTTP_STATUSES = {400, 401, 403, 404, 409, 422}


def is_retryable_error(exc: Exception) -> bool:
    """Determine if an exception represents a transient, retryable network or server failure."""
    if isinstance(exc, HTTPError):
        return exc.code in RETRYABLE_HTTP_STATUSES

    if isinstance(exc, (URLError, TimeoutError, ConnectionResetError, ConnectionRefusedError, ConnectionAbortedError)):
        return True

    # Generic string checks for transient socket errors
    msg = str(exc).lower()
    transient_indicators = [
        "timed out",
        "timeout",
        "connection reset",
        "connection refused",
        "broken pipe",
        "network unreachable",
        "remote end closed",
        "forcibly closed"
    ]
    return any(ind in msg for ind in transient_indicators)


class RetryEngine:
    """
    Executes operations with exponential backoff and jitter.
    Never busy-loops. Respects max retry limit and backoff caps.
    """

    def __init__(
        self,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        factor: float = 2.0,
        jitter: bool = True,
        max_retries: int = 5
    ):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.factor = factor
        self.jitter = jitter
        self.max_retries = max_retries
        self.logger = get_logger()

    def calculate_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay with jitter: delay = min(max_delay, base * factor^attempt)."""
        raw_delay = self.base_delay * (self.factor ** (attempt - 1))
        capped = min(self.max_delay, raw_delay)
        if self.jitter:
            # Full jitter: uniform between base_delay and capped
            return random.uniform(self.base_delay * 0.5, capped)
        return capped

    compute_delay = calculate_delay

    def execute_with_retry(
        self,
        operation: Callable[[], T],
        operation_name: str = "Operation",
        max_retries: Optional[int] = None,
        on_retry: Optional[Callable[[int, Exception, float], None]] = None
    ) -> T:
        """
        Execute callable with retries for transient failures.
        Non-retryable failures fail immediately.
        """
        effective_max_retries = max_retries if max_retries is not None else self.max_retries
        attempt = 0
        last_exception: Optional[Exception] = None

        while attempt <= effective_max_retries:
            attempt += 1
            try:
                return operation()
            except Exception as e:
                last_exception = e
                if not is_retryable_error(e):
                    self.logger.error(f"{operation_name} failed with non-retryable error: {e}")
                    raise

                if attempt > effective_max_retries:
                    self.logger.error(f"{operation_name} failed after {effective_max_retries} retries: {e}")
                    raise

                delay = self.calculate_delay(attempt)
                self.logger.warning(
                    f"{operation_name} transient failure (attempt {attempt}/{max_retries}): {e}. "
                    f"Retrying in {round(delay, 2)}s..."
                )

                if on_retry:
                    try:
                        on_retry(attempt, e, delay)
                    except Exception as cb_err:
                        self.logger.warning(f"Error in on_retry callback: {cb_err}")

                time.sleep(delay)

        if last_exception:
            raise last_exception
        raise RuntimeError(f"{operation_name} failed unexpectedly")

    execute = execute_with_retry


class NonRetryableError(Exception):
    """Raised when an operation encounters an unrecoverable condition."""
    pass
