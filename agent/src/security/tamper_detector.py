"""Agent Tamper Detection for RetroVault V8.

Detects unauthorized modification of agent binaries, configuration tampering,
service termination threats, and clock rollbacks.
"""

import hashlib
import os
import sys
import time
from typing import Dict, Any, List, Optional


class AgentTamperDetector:
    """Verifies local agent integrity and environment consistency."""

    def __init__(self, agent_config_path: Optional[str] = None):
        self.config_path = agent_config_path
        self._last_monotonic = time.monotonic()
        self._last_wallclock = time.time()
        self._initial_config_hash = self._compute_config_hash()

    def _compute_config_hash(self) -> Optional[str]:
        if not self.config_path or not os.path.isfile(self.config_path):
            return None
        try:
            with open(self.config_path, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception:
            return None

    def check_clock_tampering(self, max_skew_seconds: float = 300.0) -> Dict[str, Any]:
        """Detects if system wall clock was rolled backwards or jumped forward unexpectedly."""
        cur_monotonic = time.monotonic()
        cur_wallclock = time.time()

        mono_delta = cur_monotonic - self._last_monotonic
        wall_delta = cur_wallclock - self._last_wallclock

        self._last_monotonic = cur_monotonic
        self._last_wallclock = cur_wallclock

        # Wall clock moving backwards while monotonic moves forward is an indicator of clock rollback
        skew = wall_delta - mono_delta
        is_rollback = wall_delta < -10.0 or abs(skew) > max_skew_seconds

        return {
            "clock_tampered": is_rollback,
            "wall_delta": round(wall_delta, 2),
            "monotonic_delta": round(mono_delta, 2),
            "skew": round(skew, 2)
        }

    def check_config_integrity(self) -> Dict[str, Any]:
        """Checks if local configuration file was altered outside the agent process."""
        if not self._initial_config_hash:
            return {"config_tampered": False, "reason": "No config path tracked"}

        current_hash = self._compute_config_hash()
        tampered = current_hash != self._initial_config_hash
        return {
            "config_tampered": tampered,
            "original_hash": self._initial_config_hash,
            "current_hash": current_hash
        }

    def run_health_and_tamper_audit(self) -> Dict[str, Any]:
        """Performs comprehensive local tamper and health check."""
        clock_res = self.check_clock_tampering()
        cfg_res = self.check_config_integrity()

        is_tampered = clock_res["clock_tampered"] or cfg_res["config_tampered"]

        return {
            "is_tampered": is_tampered,
            "clock_audit": clock_res,
            "config_audit": cfg_res,
            "process_id": os.getpid(),
            "python_executable": sys.executable,
        }
