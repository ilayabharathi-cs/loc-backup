"""Configuration management for the RetroVault Universal Windows Backup Agent."""

import os
import json
from typing import Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict
from agent.src.utils.windows import get_programdata_path
from agent.src.utils.validation import is_valid_server_url


def get_default_config_path() -> str:
    """Return canonical path to config.json under ProgramData."""
    program_data = get_programdata_path()
    return os.path.join(program_data, "RetroVault", "agent", "config.json")


class AgentConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    server_url: str = Field(default="http://127.0.0.1:8000", description="Backend control plane URL")
    heartbeat_interval_seconds: int = Field(default=30, ge=5, le=3600, description="Heartbeat interval in seconds")
    log_level: str = Field(default="INFO", description="Logging level: DEBUG, INFO, WARNING, ERROR")
    request_timeout_seconds: int = Field(default=10, ge=1, le=120, description="HTTP timeout in seconds")
    max_retries: int = Field(default=5, ge=1, le=20, description="Max connection retries")
    verify_ssl: bool = Field(default=True, description="Verify SSL certificates for HTTPS")
    agent_version: str = Field(default="1.0.0", description="Agent release version")
    consistency_mode: str = Field(default="VSS_WHEN_REQUIRED", description="Consistency mode: LIVE, VSS_WHEN_REQUIRED, VSS_REQUIRED")
    enable_vss: bool = Field(default=True, description="Enable Volume Shadow Copy Service integration")
    enable_usn_journal: bool = Field(default=True, description="Enable NTFS USN Journal optimization")
    chunk_size: int = Field(default=4194304, ge=65536, le=67108864, description="Chunk size in bytes for resumable upload")
    retry_backoff_max_seconds: int = Field(default=60, ge=1, le=600, description="Maximum exponential retry backoff delay")
    checkpoint_interval_seconds: int = Field(default=5, ge=1, le=120, description="Checkpoint flush interval in seconds")
    resume_interrupted_runs: bool = Field(default=True, description="Automatically resume interrupted runs on startup")
    state_dir: Optional[str] = Field(default=None, description="Custom state directory for checkpoints")

    @field_validator("server_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        trimmed = v.strip().rstrip("/")
        if not is_valid_server_url(trimmed):
            raise ValueError(f"Invalid server_url: '{v}'. Must be an HTTP or HTTPS URL.")
        return trimmed

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper_v = v.strip().upper()
        if upper_v not in valid_levels:
            return "INFO"
        return upper_v


def load_config(custom_path: Optional[str] = None) -> AgentConfig:
    """Load configuration from custom_path, standard ProgramData path, or local fallback."""
    candidate_paths = []
    if custom_path:
        candidate_paths.append(os.path.abspath(custom_path))
    
    candidate_paths.append(get_default_config_path())
    candidate_paths.append(os.path.abspath("config.json"))
    candidate_paths.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.example.json"))

    for path in candidate_paths:
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return AgentConfig(**data)
            except Exception:
                # Corrupt or invalid JSON; try next candidate or fallback
                pass

    # Read from environment variables if set
    env_server = os.environ.get("RETROVAULT_SERVER_URL")
    if env_server and is_valid_server_url(env_server):
        return AgentConfig(server_url=env_server)

    return AgentConfig()
