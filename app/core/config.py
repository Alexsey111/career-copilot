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


def _is_loopback_origin(origin: str) -> bool:
    """True for localhost / 127.0.0.1 / ::1 origins (exempt from HTTPS-only)."""
    lowered = origin.lower()
    return (
        "://localhost" in lowered
        or "://localhost." in lowered  # localhost subdomains
        or "://127.0.0.1" in lowered
        or "://[::1]" in lowered
    )


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

    allowed_hosts_raw: str = Field(default="*", alias="ALLOWED_HOSTS")

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
    # Local filesystem storage root (STORAGE_MODE=local). Только для dev/test.
    local_storage_root: str = Field(default="./.local-storage", alias="LOCAL_STORAGE_ROOT")

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

    field_encryption_keys_raw: str = Field(default="", alias="FIELD_ENCRYPTION_KEYS")

    ai_default_model: str = Field(default="gigachat-pro", alias="AI_DEFAULT_MODEL")
    ai_provider: LLMProvider = Field(default="gigachat", alias="AI_PROVIDER")
    ai_fallback_provider: LLMProvider | None = Field(default=None, alias="AI_FALLBACK_PROVIDER")
    ai_fallback_model: str | None = Field(default=None, alias="AI_FALLBACK_MODEL")
    ai_request_timeout: float = Field(default=30.0, alias="AI_REQUEST_TIMEOUT")
    ai_max_retries: int = Field(default=3, alias="AI_MAX_RETRIES")
    ai_temperature: float = Field(default=0.1, alias="AI_TEMPERATURE")
    # Cost accounting (ТЗ §3.4): стоимость за 1000 токенов в валюте учёта.
    # 0.0 по умолчанию — учёт отключён, пока ставки не заданы.
    ai_cost_per_1k_input: float = Field(default=0.0, alias="AI_COST_PER_1K_INPUT")
    ai_cost_per_1k_output: float = Field(default=0.0, alias="AI_COST_PER_1K_OUTPUT")
    # AI response cache (ТЗ §3.4 «caching»). По умолчанию выключен.
    ai_cache_enabled: bool = Field(default=False, alias="AI_CACHE_ENABLED")
    ai_cache_max_size: int = Field(default=256, alias="AI_CACHE_MAX_SIZE")

    gigachat_api_key: str | None = Field(default=None, alias="GIGACHAT_API_KEY")
    gigachat_base_url: str | None = Field(default=None, alias="GIGACHAT_BASE_URL")

    oauth_google_client_id: str | None = Field(default=None, alias="OAUTH_GOOGLE_CLIENT_ID")
    oauth_google_client_secret: str | None = Field(default=None, alias="OAUTH_GOOGLE_CLIENT_SECRET")
    oauth_github_client_id: str | None = Field(default=None, alias="OAUTH_GITHUB_CLIENT_ID")
    oauth_github_client_secret: str | None = Field(default=None, alias="OAUTH_GITHUB_CLIENT_SECRET")
    oauth_redirect_base_url: str = Field(default="http://localhost:3000", alias="OAUTH_REDIRECT_BASE_URL")

    # Billing (ТЗ §3.5). Stripe official SDK. Secrets empty by default —
    # validate_runtime_safety requires them in production.
    stripe_secret_key: str | None = Field(default=None, alias="STRIPE_SECRET_KEY")
    stripe_webhook_secret: str | None = Field(default=None, alias="STRIPE_WEBHOOK_SECRET")
    stripe_webhook_tolerance: int = Field(default=300, alias="STRIPE_WEBHOOK_TOLERANCE")
    stripe_price_paid_monthly_id: str | None = Field(
        default=None, alias="STRIPE_PRICE_PAID_MONTHLY_ID"
    )
    # Display-only amount (minor units / cents) for the paid monthly plan.
    stripe_paid_monthly_amount: int = Field(default=0, alias="STRIPE_PAID_MONTHLY_AMOUNT")
    stripe_paid_plan_name: str = Field(default="paid_monthly", alias="STRIPE_PAID_PLAN_NAME")
    # Free-tier usage quotas (rolling window = billing_quota_window_days).
    # paid_monthly = unlimited (limits not applied). Defaults are conservative;
    # tests override via env to keep existing AI/upload tests under the cap.
    billing_free_tier_ai_requests_limit: int = Field(
        default=50, alias="BILLING_FREE_TIER_AI_REQUESTS_LIMIT"
    )
    billing_free_tier_doc_uploads_limit: int = Field(
        default=10, alias="BILLING_FREE_TIER_DOC_UPLOADS_LIMIT"
    )
    billing_free_tier_generated_outputs_limit: int = Field(
        default=5, alias="BILLING_FREE_TIER_GENERATED_OUTPUTS_LIMIT"
    )
    # Demo-режим: лимит импорта вакансий (3) в коротком скользящем окне. Окно —
    # секунды, не дни: ``billing_quota_window_days`` здесь не применяется.
    # 3 импорта → 402, затем ждать, пока старые выпадут из окна (≈ час).
    billing_free_tier_vacancy_imports_limit: int = Field(
        default=3, alias="BILLING_FREE_TIER_VACANCY_IMPORTS_LIMIT"
    )
    demo_vacancy_import_window_seconds: int = Field(
        default=3600, alias="DEMO_VACANCY_IMPORT_WINDOW_SECONDS"
    )
    billing_quota_window_days: int = Field(default=30, alias="BILLING_QUOTA_WINDOW_DAYS")
    billing_checkout_success_url: str = Field(
        default="http://localhost:3000/billing/success", alias="BILLING_CHECKOUT_SUCCESS_URL"
    )
    billing_checkout_cancel_url: str = Field(
        default="http://localhost:3000/billing/cancel", alias="BILLING_CHECKOUT_CANCEL_URL"
    )
    billing_portal_return_url: str = Field(
        default="http://localhost:3000/billing", alias="BILLING_PORTAL_RETURN_URL"
    )

    # Telegram companion (ТЗ §3.6). Bot API через httpx напрямую. Секреты
    # (bot_token, webhook_secret) хранятся только в settings/env, НИКОГДА в БД.
    # ``telegram_chat_id`` на User — plain String (pseudonymous identifier, как
    # ``oauth_provider_id``), нужен для webhook lookup chat_id → user.
    telegram_bot_token: str | None = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    telegram_webhook_secret: str | None = Field(
        default=None, alias="TELEGRAM_WEBHOOK_SECRET"
    )
    telegram_bot_username: str | None = Field(default=None, alias="TELEGRAM_BOT_USERNAME")
    telegram_link_token_ttl_minutes: int = Field(
        default=15, alias="TELEGRAM_LINK_TOKEN_TTL_MINUTES"
    )
    # Global feature flag для proactive push (Celery beat). Per-user opt-in —
    # отдельная колонка ``User.telegram_dispatch_enabled``.
    telegram_dispatch_enabled: bool = Field(default=False, alias="TELEGRAM_DISPATCH_ENABLED")
    # Webhook URL для setup-скрипта setWebhook (не для runtime-валидации).
    telegram_webhook_url: str | None = Field(default=None, alias="TELEGRAM_WEBHOOK_URL")

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

    @property
    def field_encryption_keys(self) -> list[str]:
        return [key.strip() for key in self.field_encryption_keys_raw.split(",") if key.strip()]

    @property
    def allowed_hosts(self) -> list[str]:
        return [host.strip() for host in self.allowed_hosts_raw.split(",") if host.strip()] or ["*"]

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

            if not self.minio_secure:
                raise ValueError("MINIO_SECURE must be true in production (encrypt data in transit to object storage)")

            if self.storage_mode == "local":
                raise ValueError("STORAGE_MODE=local is not allowed in production")

            if "*" in self.cors_allowed_origins:
                raise ValueError("CORS_ALLOWED_ORIGINS cannot contain '*' in production")

            # Non-localhost CORS origins must be HTTPS in production (ФЗ-152 ст.19:
            # protection of personal data in transit). localhost/loopback is exempt.
            for origin in self.cors_allowed_origins:
                if origin.startswith("http://") and not _is_loopback_origin(origin):
                    raise ValueError(
                        f"CORS_ALLOWED_ORIGINS must use HTTPS in production: {origin!r}"
                    )

            if self.ai_provider == "mock":
                raise ValueError("AI_PROVIDER=mock is not allowed in production")

            if self.ai_fallback_provider == "mock":
                raise ValueError("AI_FALLBACK_PROVIDER=mock is not allowed in production")

            unsafe_encryption_keys = {"", "dev-fernet-key"}
            if (
                not self.field_encryption_keys
                or all(k in unsafe_encryption_keys for k in self.field_encryption_keys)
            ):
                raise ValueError("FIELD_ENCRYPTION_KEYS is missing in production")
            try:
                from cryptography.fernet import Fernet

                for key in self.field_encryption_keys:
                    Fernet(key.encode())
            except Exception as exc:  # noqa: BLE001 - surface any invalid key clearly
                raise ValueError("FIELD_ENCRYPTION_KEYS contains an invalid Fernet key") from exc

            # Billing (ТЗ §3.5): Stripe secrets and the paid plan price id are
            # required in production so billing can control access and verify
            # webhook signatures.
            if not self.stripe_secret_key:
                raise ValueError("STRIPE_SECRET_KEY is required in production")
            if not self.stripe_webhook_secret:
                raise ValueError("STRIPE_WEBHOOK_SECRET is required in production")
            if not self.stripe_price_paid_monthly_id:
                raise ValueError("STRIPE_PRICE_PAID_MONTHLY_ID is required in production")

            # Telegram companion (ТЗ §3.6): если proactive push включён,
            # bot_token + webhook_secret + bot_username обязательны в prod
            # (webhook-секрет проверяется в /webhooks/telegram по заголовку
            # X-Telegram-Bot-Api-Secret-Token). Секреты — только в env, не в БД.
            if self.telegram_dispatch_enabled:
                if not self.telegram_bot_token:
                    raise ValueError(
                        "TELEGRAM_BOT_TOKEN is required when TELEGRAM_DISPATCH_ENABLED in production"
                    )
                if not self.telegram_webhook_secret:
                    raise ValueError(
                        "TELEGRAM_WEBHOOK_SECRET is required when TELEGRAM_DISPATCH_ENABLED in production"
                    )
                if not self.telegram_bot_username:
                    raise ValueError(
                        "TELEGRAM_BOT_USERNAME is required when TELEGRAM_DISPATCH_ENABLED in production"
                    )

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
