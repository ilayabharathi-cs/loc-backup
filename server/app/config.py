from typing import List, Union, Optional
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import json
import os
import secrets
import logging

logger = logging.getLogger("retrovault.config")

class Settings(BaseSettings):
    PROJECT_NAME: str = "RetroVault Local Backup Control Plane"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "production"
    DEBUG: bool = False

    # Database: Supports PostgreSQL for production and SQLite for local development
    DATABASE_URL: str = "sqlite:///./backup.db"

    # Security
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Server Networking & Ports
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_PATH: Optional[str] = None
    TEMP_PATH: Optional[str] = None

    # Storage Repository Paths (Cross-Platform)
    RETROVAULT_REPOSITORY_PATH: Optional[str] = None
    RETROVAULT_REPOSITORY_ROOT: Optional[str] = None
    BACKUP_REPOSITORY_PATH: Optional[str] = None

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        # Enforce secure JWT Secret in production
        if not self.JWT_SECRET_KEY or self.JWT_SECRET_KEY == "retrovault_super_secret_jwt_key_enterprise_1995_change_in_production":
            if self.ENVIRONMENT.lower() in ("production", "prod"):
                # In production generate ephemeral random secret if unset to prevent well-known default vulnerability
                generated = secrets.token_urlsafe(64)
                self.JWT_SECRET_KEY = generated
                logger.warning(
                    "PRODUCTION WARNING: JWT_SECRET_KEY was unset or using insecure default! "
                    "Generated dynamic cryptographically secure key for session."
                )
            else:
                self.JWT_SECRET_KEY = "retrovault_dev_secret_key_change_in_production_1995"

        # Production DEBUG guard
        if self.ENVIRONMENT.lower() in ("production", "prod") and self.DEBUG:
            logger.warning("PRODUCTION WARNING: DEBUG=True is active in production environment. Enforcing DEBUG=False.")
            self.DEBUG = False

        return self

    def get_repository_root(self) -> str:
        """Resolve valid and writable repository root path across Linux and Windows."""
        import platform
        candidates = []
        # 1. Explicit Environment Config
        if self.RETROVAULT_REPOSITORY_PATH:
            candidates.append(self.RETROVAULT_REPOSITORY_PATH)
        if self.RETROVAULT_REPOSITORY_ROOT:
            candidates.append(self.RETROVAULT_REPOSITORY_ROOT)
        if self.BACKUP_REPOSITORY_PATH:
            candidates.append(self.BACKUP_REPOSITORY_PATH)

        # 2. Local relative repository directory
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidates.append(os.path.join(base_dir, "repository"))

        # 3. OS-standard default locations
        if platform.system() == "Windows":
            candidates.append(r"C:\RetroVault\Repository")
            candidates.append(r"D:\RetroVaultRepository")
        else:
            candidates.append("/var/lib/retrovault/repository")
            candidates.append("/data/retrovault/cas")

        for path in candidates:
            try:
                norm = os.path.abspath(path)
                os.makedirs(norm, exist_ok=True)
                test_file = os.path.join(norm, ".test_write.tmp")
                with open(test_file, "w") as f:
                    f.write("test")
                os.remove(test_file)
                return norm
            except (PermissionError, OSError):
                continue

        # 4. Safe temp directory fallback
        import tempfile
        fallback = os.path.join(self.TEMP_PATH or tempfile.gettempdir(), "RetroVaultRepository")
        os.makedirs(fallback, exist_ok=True)
        return fallback

    def get_system_info(self) -> dict:
        """Return platform and runtime metadata."""
        import platform
        import sys
        db_type = "postgresql" if "postgres" in self.DATABASE_URL.lower() else "sqlite"
        return {
            "server_platform": platform.system(),
            "server_os_release": platform.release(),
            "server_arch": platform.machine(),
            "python_version": sys.version.split()[0],
            "database_engine": db_type,
            "repository_root": self.get_repository_root(),
            "environment": self.ENVIRONMENT,
            "debug": self.DEBUG
        }

    # CORS
    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, str) and v.startswith("["):
            return json.loads(v)
        return v

    @field_validator("DATABASE_URL", mode="after")
    @classmethod
    def resolve_sqlite_url(cls, v: str) -> str:
        if v.startswith("sqlite:///./") or v.startswith("sqlite:////./"):
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_rel = v.split("sqlite:///./")[-1].lstrip("/")
            db_path = os.path.join(base_dir, db_rel).replace("\\", "/")
            return f"sqlite:///{db_path}"
        return v

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

