from __future__ import annotations

import os
from types import SimpleNamespace

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.config import get_settings
from app.core.rate_limit import clear_rate_limits_for_tests
from app.main import app
from app.db.session import get_db_session


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    get_settings.cache_clear()
    clear_rate_limits_for_tests()
    yield
    get_settings.cache_clear()
    clear_rate_limits_for_tests()


@pytest.mark.asyncio
async def test_login_rate_limit_returns_429(prepare_test_db):
    os.environ["RATE_LIMIT_ENABLED"] = "true"
    os.environ["RATE_LIMIT_LOGIN_LIMIT"] = "1"
    os.environ["RATE_LIMIT_LOGIN_WINDOW_SECONDS"] = "60"
    get_settings.cache_clear()
    clear_rate_limits_for_tests()

    test_db_url = os.environ.get("TEST_DATABASE_URL", os.environ.get("DATABASE_URL"))
    engine = create_async_engine(test_db_url)
    TestSession = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with TestSession() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {"email": "missing@example.com", "password": "wrong-password"}
            first = await client.post("/api/v1/auth/login", json=payload)
            second = await client.post("/api/v1/auth/login", json=payload)
            assert first.status_code in {401, 422}
            assert second.status_code == 429
            assert second.json()["error"]["code"] == "rate_limit_exceeded"
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        await engine.dispose()

    os.environ.pop("RATE_LIMIT_ENABLED", None)
    os.environ.pop("RATE_LIMIT_LOGIN_LIMIT", None)
    os.environ.pop("RATE_LIMIT_LOGIN_WINDOW_SECONDS", None)
    get_settings.cache_clear()
    clear_rate_limits_for_tests()


@pytest.mark.asyncio
async def test_rate_limit_can_be_disabled(prepare_test_db):
    os.environ["RATE_LIMIT_ENABLED"] = "false"
    os.environ["RATE_LIMIT_LOGIN_LIMIT"] = "1"
    os.environ["RATE_LIMIT_LOGIN_WINDOW_SECONDS"] = "60"
    get_settings.cache_clear()
    clear_rate_limits_for_tests()

    test_db_url = os.environ.get("TEST_DATABASE_URL", os.environ.get("DATABASE_URL"))
    engine = create_async_engine(test_db_url)
    TestSession = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with TestSession() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {"email": "missing2@example.com", "password": "wrong-password"}
            first = await client.post("/api/v1/auth/login", json=payload)
            second = await client.post("/api/v1/auth/login", json=payload)
            assert first.status_code in {401, 422}
            assert second.status_code in {401, 422}
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        await engine.dispose()

    os.environ.pop("RATE_LIMIT_ENABLED", None)
    os.environ.pop("RATE_LIMIT_LOGIN_LIMIT", None)
    os.environ.pop("RATE_LIMIT_LOGIN_WINDOW_SECONDS", None)
    get_settings.cache_clear()
    clear_rate_limits_for_tests()
