"""Agent Security Module for RetroVault V7 & V8."""

try:
    from security.credential_manager import AgentCredentialManager
    from security.entropy_sampler import AgentEntropySampler
    from security.tamper_detector import AgentTamperDetector
except ImportError:
    from agent.src.security.credential_manager import AgentCredentialManager
    from agent.src.security.entropy_sampler import AgentEntropySampler
    from agent.src.security.tamper_detector import AgentTamperDetector

__all__ = ["AgentCredentialManager", "AgentEntropySampler", "AgentTamperDetector"]
