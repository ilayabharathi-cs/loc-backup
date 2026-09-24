"""Agent Tests for RetroVault V8: Tamper Detection & Entropy Sampling."""

import os
import sys
import tempfile
import time
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from agent.src.security.entropy_sampler import AgentEntropySampler
from agent.src.security.tamper_detector import AgentTamperDetector


def test_agent_entropy_sampler():
    # 1. Plain text file
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as f:
        f.write("Standard repetitive log and text entry for agent testing.\n" * 100)
        txt_path = f.name

    # 2. Pseudo-random high entropy file
    with tempfile.NamedTemporaryFile("wb", delete=False, suffix=".dat") as f:
        f.write(os.urandom(8192))
        rand_path = f.name

    try:
        txt_ent = AgentEntropySampler.sample_file(txt_path)
        assert txt_ent is not None
        assert txt_ent < 5.0

        rand_ent = AgentEntropySampler.sample_file(rand_path)
        assert rand_ent is not None
        assert rand_ent > 7.5
    finally:
        if os.path.exists(txt_path):
            os.remove(txt_path)
        if os.path.exists(rand_path):
            os.remove(rand_path)


def test_agent_tamper_detector_config_integrity():
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as f:
        f.write('{"agent_name": "agent-1", "server_url": "http://localhost:8000"}')
        cfg_path = f.name

    try:
        detector = AgentTamperDetector(agent_config_path=cfg_path)
        audit1 = detector.check_config_integrity()
        assert audit1["config_tampered"] is False

        # Simulate external tampering
        time.sleep(0.05)
        with open(cfg_path, "w") as f:
            f.write('{"agent_name": "hacked-agent", "server_url": "http://evil.com"}')

        audit2 = detector.check_config_integrity()
        assert audit2["config_tampered"] is True

        # Comprehensive health & tamper audit
        full_audit = detector.run_health_and_tamper_audit()
        assert full_audit["is_tampered"] is True
    finally:
        if os.path.exists(cfg_path):
            os.remove(cfg_path)
