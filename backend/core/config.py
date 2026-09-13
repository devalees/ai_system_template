"""Core platform configuration using Pydantic Settings."""

import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration parameters for the Sovereign Headless Backend."""

    # Platform Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # ASGI Server
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000

    # PostgreSQL Database
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "sovereign"
    POSTGRES_PASSWORD: str = "sovereign_secret_pass_2026"
    POSTGRES_DB: str = "sovereign_db"
    DATABASE_URL: str = "postgresql+asyncpg://sovereign:sovereign_secret_pass_2026@postgres:5432/sovereign_db"

    # Redis & Celery
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/2"

    # Security & Tokens
    JWT_SECRET_KEY: str = "sovereign_jwt_secret_dev_key_2026_change_in_prod"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Hermes AI Agent Gateway
    HERMES_GATEWAY_URL: str = "http://host.docker.internal:8643"
    HERMES_API_KEY: str = "hermes_agent_secret_key_prod_2026_audit"
    LANGFUSE_HOST: str = "http://host.docker.internal:3100"

    # Storage & Attachments
    FILESTORE_PATH: str = "/app/filestore"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
