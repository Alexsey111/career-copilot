import pytest
from fastapi import HTTPException

from app.services.vacancy_import_service import VacancyImportService


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