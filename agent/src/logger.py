"""Structured and masked logging for RetroVault Backup Agent."""

import os
import re
import sys
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional
from agent.src.utils.windows import get_programdata_path
from agent.src.utils.filesystem import ensure_directory


def get_default_log_dir() -> str:
    """Return standard log directory under ProgramData."""
    program_data = get_programdata_path()
    return os.path.join(program_data, "RetroVault", "agent", "logs")


class SensitiveMaskingFormatter(logging.Formatter):
    """Formatter that intercepts and masks sensitive tokens, passwords, and secrets."""

    PATTERNS = [
        (re.compile(r'(password|passwd|secret|token|jwt|authorization)\s*[:=]\s*["\']?([^"\'\s,]+)', re.IGNORECASE), r'\1=***REDACTED***'),
        (re.compile(r'Bearer\s+[A-Za-z0-9\-._~+/]+=*', re.IGNORECASE), 'Bearer ***REDACTED***'),
    ]

    def format(self, record: logging.LogRecord) -> str:
        orig = super().format(record)
        for pattern, repl in self.PATTERNS:
            orig = pattern.sub(repl, orig)
        return orig


_logger_instance: Optional[logging.Logger] = None


def setup_logger(log_level: str = "INFO", log_dir: Optional[str] = None) -> logging.Logger:
    """Configure and return the RetroVault agent logger."""
    global _logger_instance
    if _logger_instance is not None:
        return _logger_instance

    logger = logging.getLogger("retrovault.agent")
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(numeric_level)
    logger.propagate = False

    # Avoid adding duplicate handlers
    if not logger.handlers:
        fmt_str = "%(asctime)s [%(levelname)s] [%(name)s.%(module)s] %(message)s"
        formatter = SensitiveMaskingFormatter(fmt_str)

        # 1. Console Stream Handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # 2. Rotating File Handler
        try:
            target_log_dir = log_dir or get_default_log_dir()
            ensure_directory(target_log_dir)
            log_file = os.path.join(target_log_dir, "agent.log")

            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10 MB
                backupCount=5,
                encoding="utf-8"
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            logger.warning(f"Could not initialize rotating file logger: {e}. Falling back to console only.")

    _logger_instance = logger
    return logger


def get_logger() -> logging.Logger:
    """Retrieve existing logger or initialize with default INFO level."""
    global _logger_instance
    if _logger_instance is None:
        return setup_logger()
    return _logger_instance
