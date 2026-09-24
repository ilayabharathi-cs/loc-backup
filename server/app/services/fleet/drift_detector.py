"""Configuration Drift Detection for RetroVault V8.

Compares active agent telemetry against assigned policies and detects discrepancies
in paths, throttling limits, compression, and encryption settings.
"""

import datetime
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.security_v8_models import ConfigurationDrift, SecurityEvent
from app.services.fleet.policy_orchestrator import PolicyOrchestrator

logger = logging.getLogger(__name__)


class DriftDetector:
    """Detects configuration differences between agent reported state and assigned policy."""

    def __init__(self, db: Session):
        self.db = db
        self.orchestrator = PolicyOrchestrator(db)

    def detect_drift(self, client_id: int, agent_reported_config: Dict[str, Any]) -> List[ConfigurationDrift]:
        """Compares agent-reported settings against effective server policy."""
        client = self.db.query(Client).filter(Client.id == client_id).first()
        if not client:
            return []

        effective = self.orchestrator.resolve_effective_policy(client_id)
        if "error" in effective:
            return []

        drifts_detected: List[ConfigurationDrift] = []

        # 1. Compare Compression Setting
        exp_comp = str(effective.get("compression_enabled", True)).lower()
        act_comp = str(agent_reported_config.get("compression_enabled", exp_comp)).lower()
        if exp_comp != act_comp:
            drifts_detected.append(ConfigurationDrift(
                client_id=client_id,
                drift_type="COMPRESSION_MISMATCH",
                expected_value=exp_comp,
                actual_value=act_comp,
                severity="WARNING"
            ))

        # 2. Compare Encryption Setting
        exp_enc = str(effective.get("encryption_enabled", True)).lower()
        act_enc = str(agent_reported_config.get("encryption_enabled", exp_enc)).lower()
        if exp_enc != act_enc:
            drifts_detected.append(ConfigurationDrift(
                client_id=client_id,
                drift_type="ENCRYPTION_DISABLED",
                expected_value=exp_enc,
                actual_value=act_enc,
                severity="HIGH"
            ))

        # 3. Compare CPU Limit
        exp_cpu = str(effective.get("cpu_limit_percent", 10))
        act_cpu = str(agent_reported_config.get("cpu_limit_percent", exp_cpu))
        if exp_cpu != act_cpu:
            drifts_detected.append(ConfigurationDrift(
                client_id=client_id,
                drift_type="CPU_THROTTLE_DRIFT",
                expected_value=exp_cpu,
                actual_value=act_cpu,
                severity="LOW"
            ))

        # Record drifts in database
        for d in drifts_detected:
            self.db.add(d)

        if drifts_detected:
            event = SecurityEvent(
                event_type="CONFIG_DRIFT",
                severity="HIGH" if any(x.severity == "HIGH" for x in drifts_detected) else "MEDIUM",
                client_id=client_id,
                score=50,
                description=f"Configuration drift detected on Client #{client_id}: {len(drifts_detected)} mismatches.",
                status="OPEN"
            )
            self.db.add(event)

        self.db.commit()
        return drifts_detected
