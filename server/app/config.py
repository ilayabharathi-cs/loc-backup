from typing import List, Union, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import json
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "RetroVault Backup Control Plane"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "sqlite:///./backup.db"

    # Security
    JWT_SECRET_KEY: str = "retrovault_super_secret_jwt_key_enterprise_1995_change_in_production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Storage Repository Path
    RETROVAULT_REPOSITORY_ROOT: Optional[str] = None
    BACKUP_REPOSITORY_PATH: str = "D:\\RetroVaultRepository"

    def get_repository_root(self) -> str:
        """Resolve valid and writable repository root path with fallback."""
        candidates = []
        if self.RETROVAULT_REPOSITORY_ROOT:
            candidates.append(self.RETROVAULT_REPOSITORY_ROOT)
        if self.BACKUP_REPOSITORY_PATH:
            candidates.append(self.BACKUP_REPOSITORY_PATH)

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidates.append(os.path.join(base_dir, "repository"))

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

        # Ultimate fallback to tempdir if all else fails
        import tempfile
        fallback = os.path.join(tempfile.gettempdir(), "RetroVaultRepository")
        os.makedirs(fallback, exist_ok=True)
        return fallback

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
