from __future__ import annotations

from types import SimpleNamespace

import pytest
import httpx
from fastapi import HTTPException

from app.services.hh_vacancy_import_service import HHVacancyImportService


def test_extract_hh_vacancy_id_from_url() -> None:
    service = HHVacancyImportService()

    assert (
        service.extract_vacancy_id(
            "https://barnaul.hh.ru/vacancy/133412268?hhtmFrom=favorite_vacancy_list"
        )
        == "133412268"
    )


def test_extract_hh_vacancy_id_rejects_non_hh_vacancy_url() -> None:
    service = HHVacancyImportService()

    with pytest.raises(HTTPException) as exc:
        service.extract_vacancy_id("https://example.com/jobs/123")

    assert exc.value.status_code == 422


def test_map_hh_payload_to_import_payload() -> None:
    service = HHVacancyImportService()

    result = service.map_to_import_payload(
        {
            "id": "133412268",
            "name": "AI-специалист",
            "employer": {"name": "MakrosDigital"},
            "area": {"name": "Барановичи"},
            "description": "<p>Требования:</p><ul><li>ChatGPT</li><li>Claude</li></ul>",
            "key_skills": [{"name": "AI workflow"}, {"name": "Автоматизация"}],
            "experience": {"name": "1–3 года"},
            "employment": {"name": "Проектная работа"},
            "schedule": {"name": "Удалённая работа"},
        },
        source_url="https://barnaul.hh.ru/vacancy/133412268",
    )

    assert result["source"] == "hh"
    assert result["external_id"] == "133412268"
    assert result["title"] == "AI-специалист"
    assert result["company"] == "MakrosDigital"
    assert result["location"] == "Барановичи"
    assert "ChatGPT" in result["description_raw"]
    assert "Claude" in result["description_raw"]
    assert "AI workflow" in result["description_raw"]


@pytest.mark.asyncio
async def test_fetch_vacancy_returns_502_on_connect_error(monkeypatch) -> None:
    service = HHVacancyImportService()

    class FakeAsyncClient:
        def __init__(self, **kwargs) -> None:
            return None

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, path: str):
            raise httpx.ConnectError("dns failed", request=httpx.Request("GET", "https://api.hh.ru/vacancies/1"))

    monkeypatch.setattr(
        "app.services.hh_vacancy_import_service.httpx.AsyncClient",
        FakeAsyncClient,
    )

    with pytest.raises(HTTPException) as exc:
        await service.fetch_vacancy("https://hh.ru/vacancy/1")

    assert exc.value.status_code == 502
    assert "DNS/network error" in exc.value.detail


@pytest.mark.asyncio
async def test_fetch_vacancy_returns_504_on_timeout(monkeypatch) -> None:
    service = HHVacancyImportService()

    class FakeAsyncClient:
        def __init__(self, **kwargs) -> None:
            return None

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, path: str):
            raise httpx.TimeoutException("timeout", request=httpx.Request("GET", "https://api.hh.ru/vacancies/1"))

    monkeypatch.setattr(
        "app.services.hh_vacancy_import_service.httpx.AsyncClient",
        FakeAsyncClient,
    )

    with pytest.raises(HTTPException) as exc:
        await service.fetch_vacancy("https://hh.ru/vacancy/1")

    assert exc.value.status_code == 504
    assert "HH API request timed out" in exc.value.detail


@pytest.mark.asyncio
async def test_fetch_vacancy_uses_configured_user_agent(monkeypatch) -> None:
    service = HHVacancyImportService()
    captured: dict[str, object] = {}

    class FakeResponse:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {
                "id": 133412268,
                "name": "AI-специалист",
                "description": "<p>OK</p>",
                "employer": {"name": "MakrosDigital"},
                "area": {"name": "Барановичи"},
            }

    class FakeAsyncClient:
        def __init__(self, **kwargs) -> None:
            captured["init_kwargs"] = kwargs

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, path: str) -> FakeResponse:
            captured["path"] = path
            return FakeResponse()

    monkeypatch.setattr(
        "app.services.hh_vacancy_import_service.get_settings",
        lambda: SimpleNamespace(hh_user_agent="career-copilot/0.1 alice@example.com"),
    )
    monkeypatch.setattr(
        "app.services.hh_vacancy_import_service.httpx.AsyncClient",
        FakeAsyncClient,
    )

    payload = await service.fetch_vacancy("https://barnaul.hh.ru/vacancy/133412268")

    assert captured["path"] == "/vacancies/133412268"
    assert captured["init_kwargs"]["headers"] == {
        "HH-User-Agent": "career-copilot/0.1 alice@example.com"
    }
    assert payload["id"] == 133412268


@pytest.mark.asyncio
async def test_fetch_vacancy_returns_graceful_502_on_hh_403(monkeypatch) -> None:
    service = HHVacancyImportService()

    class FakeResponse:
        status_code = 403

        def json(self) -> dict[str, object]:
            return {"detail": "forbidden"}

    class FakeAsyncClient:
        def __init__(self, **kwargs) -> None:
            return None

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, path: str) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr(
        "app.services.hh_vacancy_import_service.httpx.AsyncClient",
        FakeAsyncClient,
    )

    with pytest.raises(HTTPException) as exc:
        await service.fetch_vacancy("https://hh.ru/vacancy/1")

    assert exc.value.status_code == 502
    assert "Используйте ручной импорт" in exc.value.detail


@pytest.mark.asyncio
async def test_fetch_vacancy_allows_contact_email_override(monkeypatch) -> None:
    service = HHVacancyImportService()
    captured: dict[str, object] = {}

    class FakeResponse:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {
                "id": 133412268,
                "name": "AI-специалист",
                "description": "<p>OK</p>",
                "employer": {"name": "MakrosDigital"},
                "area": {"name": "Барановичи"},
            }

    class FakeAsyncClient:
        def __init__(self, **kwargs) -> None:
            captured["init_kwargs"] = kwargs

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, path: str) -> FakeResponse:
            captured["path"] = path
            return FakeResponse()

    monkeypatch.setattr(
        "app.services.hh_vacancy_import_service.httpx.AsyncClient",
        FakeAsyncClient,
    )

    payload = await service.fetch_vacancy(
        "https://barnaul.hh.ru/vacancy/133412268",
        contact_email="alice@example.com",
    )

    assert captured["init_kwargs"]["headers"] == {
        "HH-User-Agent": "career-copilot/0.1 alice@example.com"
    }
    assert payload["id"] == 133412268


@pytest.mark.asyncio
async def test_fetch_vacancy_uses_current_user_email_in_hh_user_agent(monkeypatch):
    captured_headers = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"id": "123", "name": "Test vacancy"}

    class FakeAsyncClient:
        def __init__(self, *, base_url, timeout, headers):
            captured_headers.update(headers)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, path):
            assert path == "/vacancies/123"
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    service = HHVacancyImportService()
    await service.fetch_vacancy(
        "https://hh.ru/vacancy/123",
        contact_email="user@example.com",
    )

    assert captured_headers["HH-User-Agent"] == "career-copilot/0.1 user@example.com"
