from __future__ import annotations

import asyncio
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app import models  # noqa: F401
from app.api.dependencies import get_current_dev_user
from app.api.dependencies import get_current_active_user
from app.core.config import get_settings
from app.core.rate_limit import clear_rate_limits_for_tests
from app.db.base import Base
from app.db.session import get_db_session
from app.main import app
from app.models import User, UserConsent
from app.services.resume_parser_service import ResumeParserService
from app.services.storage_service import StorageService


_REQUIRED_CONSENT_TYPES = ("data_processing", "ai_generation", "profile_storage")


if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://career_user:career_pass@127.0.0.1:5434/career_copilot_test",
)


def ensure_test_database_exists(database_url: str) -> None:
    async_url = make_url(database_url)
    test_db_name = async_url.database

    if not test_db_name:
        raise RuntimeError("TEST_DATABASE_URL must include database name")

    if not re.fullmatch(r"[A-Za-z0-9_]+", test_db_name):
        raise RuntimeError(
            f"Unsupported test database name: {test_db_name!r}. "
            "Use only letters, digits, and underscores."
        )

    sync_admin_url = make_url(database_url).set(database="postgres")

    engine = create_engine(
        sync_admin_url,
        isolation_level="AUTOCOMMIT",
        future=True,
    )

    try:
        with engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
                {"db_name": test_db_name},
            ).scalar()

            if not exists:
                conn.execute(text(f'CREATE DATABASE "{test_db_name}"'))
    finally:
        engine.dispose()


ensure_test_database_exists(TEST_DATABASE_URL)

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    future=True,
    poolclass=NullPool,  # critical: do not reuse psycopg connections across loops/tests
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


def reset_database() -> None:
    ensure_test_database_exists(TEST_DATABASE_URL)


async def truncate_database() -> None:
    max_attempts = 5
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            async with test_engine.begin() as conn:
                result = await conn.execute(
                    text(
                        "SELECT tablename "
                        "FROM pg_tables "
                        "WHERE schemaname = 'public' "
                        "AND tablename <> 'alembic_version' "
                        "ORDER BY tablename"
                    )
                )
                table_names = [row[0] for row in result.fetchall()]
                if not table_names:
                    return

                quoted_tables = ", ".join(f'"{name}"' for name in table_names)
                await conn.execute(
                    text(f"TRUNCATE TABLE {quoted_tables} RESTART IDENTITY CASCADE")
                )
            return
        except OperationalError as exc:
            last_error = exc
            if "DeadlockDetected" not in str(exc):
                raise
            await asyncio.sleep(0.2 * attempt)

    if last_error is not None:
        raise last_error


@pytest_asyncio.fixture(scope="session")
async def prepare_test_db():
    await test_engine.dispose()
    reset_database()

    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    os.environ["SYNC_DATABASE_URL"] = TEST_DATABASE_URL
    get_settings.cache_clear()

    alembic_cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(alembic_cfg, "head")

    yield

    await test_engine.dispose()


@pytest_asyncio.fixture
async def db_session(prepare_test_db):
    await truncate_database()

    async with TestSessionLocal() as session:
        yield session

    await truncate_database()


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    unique_email = f"test-{uuid4().hex}@local.test"
    user = User(
        email=unique_email,
        password_hash="test-password-hash",
        auth_provider="test",
    )
    db_session.add(user)
    await db_session.flush()
    # Авто-выдача обязательных согласий (ФЗ-152) — чтобы существующие тесты,
    # использующие consent-protected эндпоинты через client-фикстуру, не
    # падали с 403. Тесты на сам enforcement выдачу не используют.
    for consent_type in _REQUIRED_CONSENT_TYPES:
        db_session.add(
            UserConsent(
                user_id=user.id,
                consent_type=consent_type,
                granted=True,
                version="1.0",
                granted_at=datetime.now(timezone.utc),
            )
        )
    await db_session.flush()
    return user


@pytest.fixture(autouse=True)
def fake_storage(monkeypatch: pytest.MonkeyPatch):
    storage: dict[str, bytes] = {}

    def upload_bytes(self, *, storage_key: str, content: bytes, content_type: str | None = None):
        storage[storage_key] = content

    def download_bytes(self, *, storage_key: str) -> bytes:
        if storage_key not in storage:
            raise FileNotFoundError(f"storage key not found: {storage_key}")
        return storage[storage_key]

    monkeypatch.setattr(StorageService, "upload_bytes", upload_bytes)
    monkeypatch.setattr(StorageService, "download_bytes", download_bytes)

    return storage


@pytest.fixture(autouse=True)
def clear_rate_limits_between_tests():
    clear_rate_limits_for_tests()
    yield
    clear_rate_limits_for_tests()


@pytest.fixture(autouse=True)
def fake_resume_parser(monkeypatch: pytest.MonkeyPatch):
    def parse(self, *, file_bytes: bytes, mime_type: str | None, filename: str):
        text = """Алексей
Перминов
г. Москва

ПРОФЕССИОНАЛЬНЫЕ НАВЫКИ
Python, SQL, FastAPI, Docker, LLM, Git

ЖЕЛАЕМАЯ ДОЛЖНОСТЬ
AI Product Engineer, Data Analyst

ОПЫТ РАБОТЫ
Acme, AI Engineer
01.01.2023 - по настоящее время

ПРОЕКТЫ
1. Создание AI-системы мониторинга безопасности
2. Анализ текстовых отзывов
"""
        return SimpleNamespace(
            text=text,
            metadata={
                "filename": filename,
                "mime_type": mime_type,
                "size_bytes": len(file_bytes),
            },
            detected_format="pdf",
        )

    monkeypatch.setattr(ResumeParserService, "parse", parse)


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, test_user: User):
    async def override_get_db_session():
        yield db_session

    test_user_id = test_user.id
    test_user_email = test_user.email

    def override_current_user():
        return SimpleNamespace(
            id=test_user_id,
            email=test_user_email,
            is_active=True,
            is_verified=True,
        )

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_current_active_user] = override_current_user
    app.dependency_overrides[get_current_dev_user] = override_current_user

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as async_client:
        yield async_client

    app.dependency_overrides.clear()
