from __future__ import annotations

import os
import re
from types import SimpleNamespace

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app import models  # noqa: F401
from app.api.dependencies import get_current_dev_user
from app.db.base import Base
from app.db.session import get_db_session
from app.main import app
from app.models import User
from app.services.resume_parser_service import ResumeParserService
from app.services.storage_service import StorageService


TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://career_user:career_pass@localhost:5432/career_copilot_test",
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

    sync_admin_url = make_url(database_url.replace("+asyncpg", "+psycopg")).set(
        database="postgres"
    )

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
    poolclass=NullPool,  # critical: do not reuse asyncpg connections across loops/tests
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def reset_database() -> None:
    async with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


@pytest_asyncio.fixture(scope="session", autouse=True)
async def prepare_test_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await test_engine.dispose()


@pytest_asyncio.fixture
async def db_session(prepare_test_db):
    await reset_database()

    async with TestSessionLocal() as session:
        yield session

    await reset_database()


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    user = User(
        email="test@local.test",
        auth_provider="test",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
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

    def override_current_user():
        return SimpleNamespace(id=test_user.id)

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_current_dev_user] = override_current_user

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as async_client:
        yield async_client

    app.dependency_overrides.clear()