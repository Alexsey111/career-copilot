"""Simple in-memory rate limiter for single-node pilot deployments."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Deque

from fastapi import Depends, Request

from app.api.exceptions import AppError
from app.core.config import get_settings


@dataclass(frozen=True, slots=True)
class RateLimitPolicy:
    name: str
    limit: int
    window_seconds: int


_hits: dict[str, Deque[float]] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    if request.client and request.client.host:
        return request.client.host

    return "unknown"


def _rate_limit_key(request: Request, policy: RateLimitPolicy) -> str:
    return f"{policy.name}:{_client_ip(request)}"


def check_rate_limit(request: Request, policy: RateLimitPolicy) -> None:
    settings = get_settings()
    if not settings.rate_limit_enabled:
        return

    now = time.monotonic()
    key = _rate_limit_key(request, policy)
    window_start = now - policy.window_seconds

    hits = _hits[key]
    while hits and hits[0] < window_start:
        hits.popleft()

    if len(hits) >= policy.limit:
        raise AppError(
            status_code=429,
            code="rate_limit_exceeded",
            message="Too many requests",
            details={
                "policy": policy.name,
                "limit": policy.limit,
                "window_seconds": policy.window_seconds,
            },
        )

    hits.append(now)


def rate_limit_dependency(policy_factory: Callable[[], RateLimitPolicy]):
    async def dependency(request: Request) -> None:
        check_rate_limit(request, policy_factory())

    return Depends(dependency)


def login_rate_limit_policy() -> RateLimitPolicy:
    settings = get_settings()
    return RateLimitPolicy(
        name="auth_login",
        limit=settings.rate_limit_login_limit,
        window_seconds=settings.rate_limit_login_window_seconds,
    )


def password_reset_rate_limit_policy() -> RateLimitPolicy:
    settings = get_settings()
    return RateLimitPolicy(
        name="password_reset_request",
        limit=settings.rate_limit_password_reset_limit,
        window_seconds=settings.rate_limit_password_reset_window_seconds,
    )


def upload_rate_limit_policy() -> RateLimitPolicy:
    settings = get_settings()
    return RateLimitPolicy(
        name="file_upload",
        limit=settings.rate_limit_upload_limit,
        window_seconds=settings.rate_limit_upload_window_seconds,
    )


login_rate_limit = rate_limit_dependency(login_rate_limit_policy)
password_reset_rate_limit = rate_limit_dependency(password_reset_rate_limit_policy)
upload_rate_limit = rate_limit_dependency(upload_rate_limit_policy)


def clear_rate_limits_for_tests() -> None:
    _hits.clear()
