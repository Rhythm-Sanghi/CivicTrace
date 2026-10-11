from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import json
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "CivicTrace"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    SECRET_KEY: str = "civictrace-insecure-development-secret-change-in-production-2026"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 # 24 hours

    # SQLite default for local zero-dependency development; PostgreSQL+PostGIS in production
    DATABASE_URL: str = "sqlite:///./civictrace_dev.db"

    STORAGE_DIR: str = "./storage"
    UPLOAD_DIR: str = "./storage/uploads"
    EXPORT_DIR: str = "./storage/exports"
    MAX_UPLOAD_SIZE_BYTES: int = 10 * 1024 * 1024 # 10MB

    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Schema management: Set to True for zero-dependency local demo/development; in production, use Alembic migrations
    AUTO_CREATE_TABLES: bool = True

    # Resolution Verification Policy Constants
    # Minimum required confirmations from distinct identities to automatically resolve an uncontested claim
    CONFIRMATIONS_REQUIRED_FOR_AUTO_RESOLVE: int = 2

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, str) and v.startswith("["):
            return json.loads(v)
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()

# Production Security Gate: Fail safely if insecure default secret is used in production
if settings.ENVIRONMENT.lower() == "production":
    if settings.SECRET_KEY == "civictrace-insecure-development-secret-change-in-production-2026":
        raise RuntimeError("FATAL: Cannot start CivicTrace in production with default insecure SECRET_KEY.")
    if settings.AUTO_CREATE_TABLES:
        raise RuntimeError("FATAL: AUTO_CREATE_TABLES must be False in production. Use Alembic migrations instead.")

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.EXPORT_DIR, exist_ok=True)
