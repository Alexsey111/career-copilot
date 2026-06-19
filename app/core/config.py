"""Application configuration."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]

AppEnv = Literal["local", "test", "staging", "prod"]
StorageMode = Literal["local", "minio", "s3"]
LLMProvider = Literal["gigachat", "openai", "mock"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="career-copilot", alias="APP_NAME")
    app_env: AppEnv = Field(default="local", alias="APP_ENV")
    app_debug: bool = Field(default=False, alias="APP_DEBUG")
    api_prefix: str = Field(default="/api/v1", alias="API_PREFIX")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    dev_auth_enabled: bool = Field(default=False, alias="DEV_AUTH_ENABLED")
    dev_user_email: str | None = Field(default=None, alias="DEV_USER_EMAIL")

    rate_limit_enabled: bool = Field(default=True, alias="RATE_LIMIT_ENABLED")
    rate_limit_login_limit: int = Field(default=10, alias="RATE_LIMIT_LOGIN_LIMIT")
    rate_limit_login_window_seconds: int = Field(default=60, alias="RATE_LIMIT_LOGIN_WINDOW_SECONDS")
    rate_limit_password_reset_limit: int = Field(default=5, alias="RATE_LIMIT_PASSWORD_RESET_LIMIT")
    rate_limit_password_reset_window_seconds: int = Field(
        default=300,
        alias="RATE_LIMIT_PASSWORD_RESET_WINDOW_SECONDS",
    )
    rate_limit_upload_limit: int = Field(default=20, alias="RATE_LIMIT_UPLOAD_LIMIT")
    rate_limit_upload_window_seconds: int = Field(default=300, alias="RATE_LIMIT_UPLOAD_WINDOW_SECONDS")

    storage_mode: StorageMode = Field(default="minio", alias="STORAGE_MODE")

    max_upload_size_bytes: int = Field(
        default=10 * 1024 * 1024,
        alias="MAX_UPLOAD_SIZE_BYTES",
    )
    allowed_upload_extensions_raw: str = Field(
        default=".pdf,.docx,.txt,.md",
        alias="ALLOWED_UPLOAD_EXTENSIONS",
    )
    allowed_upload_content_types_raw: str = Field(
        default=(
            "application/pdf,"
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document,"
            "text/plain,"
            "text/markdown,"
            "application/octet-stream"
        ),
        alias="ALLOWED_UPLOAD_CONTENT_TYPES",
    )

    cors_allowed_origins_raw: str = Field(
        default="http://localhost:8501,http://localhost:3000",
        alias="CORS_ALLOWED_ORIGINS",
    )
    cors_allow_credentials: bool = Field(default=True, alias="CORS_ALLOW_CREDENTIALS")

    backend_host: str = Field(default="0.0.0.0", alias="BACKEND_HOST")
    backend_port: int = Field(default=7000, alias="BACKEND_PORT")

    database_url: str = Field(alias="DATABASE_URL")
    sync_database_url: str = Field(alias="SYNC_DATABASE_URL")

    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")

    minio_endpoint: str = Field(default="localhost:9000", alias="MINIO_ENDPOINT")
    minio_access_key: str = Field(default="minioadmin", alias="MINIO_ACCESS_KEY")
    minio_secret_key: str = Field(default="minioadmin", alias="MINIO_SECRET_KEY")
    minio_bucket: str = Field(default="career-copilot", alias="MINIO_BUCKET")
    minio_secure: bool = Field(default=False, alias="MINIO_SECURE")

    sentry_dsn: str | None = Field(default=None, alias="SENTRY_DSN")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    openai_timeout: float = Field(default=30.0, alias="OPENAI_TIMEOUT")

    hh_user_agent: str = Field(
        default="career-copilot/0.1 contact@example.com",
        alias="HH_USER_AGENT",
    )

    jwt_secret: str = Field(alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_access_token_expire_minutes: int = Field(default=15, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=30, alias="REFRESH_TOKEN_EXPIRE_DAYS")

    ai_default_model: str = Field(default="gigachat-pro", alias="AI_DEFAULT_MODEL")
    ai_provider: LLMProvider = Field(default="gigachat", alias="AI_PROVIDER")
    ai_fallback_provider: LLMProvider | None = Field(default=None, alias="AI_FALLBACK_PROVIDER")
    ai_fallback_model: str | None = Field(default=None, alias="AI_FALLBACK_MODEL")
    ai_request_timeout: float = Field(default=30.0, alias="AI_REQUEST_TIMEOUT")
    ai_max_retries: int = Field(default=3, alias="AI_MAX_RETRIES")
    ai_temperature: float = Field(default=0.1, alias="AI_TEMPERATURE")

    gigachat_api_key: str | None = Field(default=None, alias="GIGACHAT_API_KEY")
    gigachat_base_url: str | None = Field(default=None, alias="GIGACHAT_BASE_URL")

    @property
    def is_production(self) -> bool:
        return self.app_env == "prod"

    @property
    def cors_allowed_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_allowed_origins_raw.split(",")
            if origin.strip()
        ]

    @property
    def allowed_upload_extensions(self) -> set[str]:
        return {
            ext.strip().lower()
            for ext in self.allowed_upload_extensions_raw.split(",")
            if ext.strip()
        }

    @property
    def allowed_upload_content_types(self) -> set[str]:
        return {
            item.strip().lower()
            for item in self.allowed_upload_content_types_raw.split(",")
            if item.strip()
        }

    @model_validator(mode="after")
    def validate_runtime_safety(self) -> "Settings":
        if self.is_production:
            if self.app_debug:
                raise ValueError("APP_DEBUG must be false in production")

            if self.dev_auth_enabled:
                raise ValueError("DEV_AUTH_ENABLED must be false in production")

            unsafe_jwt_values = {
                "your-super-secret-key-change-in-prod",
                "change-me",
                "secret",
                "dev-secret",
            }
            if self.jwt_secret in unsafe_jwt_values or len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET_KEY is unsafe for production")

            if self.minio_access_key == "minioadmin" or self.minio_secret_key == "minioadmin":
                raise ValueError("Default MinIO credentials are unsafe for production")

            if self.storage_mode == "local":
                raise ValueError("STORAGE_MODE=local is not allowed in production")

            if "*" in self.cors_allowed_origins:
                raise ValueError("CORS_ALLOWED_ORIGINS cannot contain '*' in production")

            if self.ai_provider == "mock":
                raise ValueError("AI_PROVIDER=mock is not allowed in production")

            if self.ai_fallback_provider == "mock":
                raise ValueError("AI_FALLBACK_PROVIDER=mock is not allowed in production")

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
