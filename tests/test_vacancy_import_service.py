import pytest
from fastapi import HTTPException
from types import SimpleNamespace

from app.services.vacancy_import_service import VacancyImportService
from app.services.vacancy_text_extractors.contracts import VacancyExtractionResult


def test_vacancy_import_rejects_question_mark_corrupted_cyrillic_text() -> None:
    service = VacancyImportService()

    with pytest.raises(HTTPException) as exc_info:
        service._ensure_text_is_not_corrupted(
            "??????????:\n"
            "- Python\n"
            "- FastAPI\n\n"
            "????? ??????:\n"
            "- Redis\n"
            "- Docker"
        )

    assert exc_info.value.status_code == 422
    assert "looks corrupted" in exc_info.value.detail


def test_vacancy_import_allows_normal_utf8_cyrillic_text() -> None:
    service = VacancyImportService()

    service._ensure_text_is_not_corrupted(
        "Требования:\n"
        "- Python\n"
        "- FastAPI\n\n"
        "Будет плюсом:\n"
        "- Redis\n"
        "- Docker"
    )


def test_vacancy_import_allows_normal_english_text_with_question_mark() -> None:
    service = VacancyImportService()

    service._ensure_text_is_not_corrupted(
        "Requirements:\n"
        "- Python\n"
        "- FastAPI\n\n"
        "Questions?\n"
        "- Can work remotely?"
    )


@pytest.mark.asyncio
async def test_vacancy_import_truncates_fetched_text_and_saves_extraction_metadata() -> None:
    service = VacancyImportService()
    captured: dict[str, object] = {}

    long_text = "A" * 130_000
    extraction_result = VacancyExtractionResult(
        title="Long Vacancy",
        text=long_text,
        extractor="trafilatura",
        extraction_method="trafilatura",
        content_length=len(long_text),
        success=True,
    )

    async def fake_fetch_url_text(source_url: str) -> VacancyExtractionResult:
        assert source_url == "https://example.com/vacancy"
        return extraction_result

    async def fake_create(session, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            id="vacancy-id",
            title=kwargs["title"],
            description_raw=kwargs["description_raw"],
            normalized_json=kwargs["normalized_json"],
        )

    class FakeSession:
        async def commit(self) -> None:
            return None

        async def refresh(self, obj) -> None:
            return None

    service._fetch_url_text = fake_fetch_url_text  # type: ignore[method-assign]
    service.vacancy_repository.create = fake_create  # type: ignore[method-assign]

    vacancy = await service.import_vacancy(
        FakeSession(),
        user_id="user-id",
        source="hh",
        source_url="https://example.com/vacancy",
        external_id=None,
        title=None,
        company=None,
        location=None,
        description_raw=None,
    )

    assert len(vacancy.description_raw) == 120_000
    assert vacancy.description_raw.endswith("A")
    assert captured["normalized_json"]["extractor"] == "trafilatura"
    assert captured["normalized_json"]["extraction_method"] == "trafilatura"
    assert captured["normalized_json"]["raw_text_length"] == 120_000


def test_truncate_large_vacancy_text() -> None:
    service = VacancyImportService()

    huge = "Python " * 50000

    result = service._truncate_text(huge)

    assert len(result) <= 120000
