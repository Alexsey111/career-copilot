"""Error monitoring setup."""

from __future__ import annotations

try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
except ModuleNotFoundError:  # pragma: no cover - dependency may be absent in local test env
    sentry_sdk = None
    FastApiIntegration = None
    LoggingIntegration = None
    SqlalchemyIntegration = None

from app.core.config import get_settings


def setup_error_monitoring() -> None:
    if sentry_sdk is None:
        return

    settings = get_settings()

    if not settings.sentry_dsn:
        return

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        release=None,
        traces_sample_rate=0.0,
        profiles_sample_rate=0.0,
        send_default_pii=False,
        integrations=[
            FastApiIntegration(),
            LoggingIntegration(
                level=None,
                event_level="ERROR",
            ),
            SqlalchemyIntegration(),
        ],
    )
