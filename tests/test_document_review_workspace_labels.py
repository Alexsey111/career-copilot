from pathlib import Path
import sys

STREAMLIT_ROOT = Path(__file__).resolve().parents[1] / "frontend" / "streamlit"
if str(STREAMLIT_ROOT) not in sys.path:
    sys.path.insert(0, str(STREAMLIT_ROOT))

from components.document_review_workspace import (  # type: ignore import-not-found
    _confidence_item_label,
    _humanize_readiness_message,
    _risk_item_label,
)


def test_confidence_item_label_uses_russian_phrasing() -> None:
    assert _confidence_item_label("backend API") == "Опыт backend и API подтверждён"


def test_risk_item_label_translates_readiness_warnings() -> None:
    assert _risk_item_label("document has coverage gaps") == (
        "Есть пробелы в покрытии требований вакансии"
    )


def test_risk_item_label_translates_resume_generation_warnings() -> None:
    assert _risk_item_label(
        "vacancy match score is currently low because structured profile coverage is still limited"
    ) == (
        "Оценка соответствия вакансии сейчас низкая, потому что структурированное покрытие профиля пока ограничено"
    )
    assert _risk_item_label(
        "missing or weakly represented vacancy keywords: FastAPI"
    ) == "Ключевые слова вакансии представлены слабо или отсутствуют"
    assert _risk_item_label(
        "resume draft is ATS-safe plaintext-oriented and not final formatted output"
    ) == (
        "Черновик резюме подготовлен в ATS-совместимом текстовом виде и пока не является финально оформленной версией"
    )


def test_readiness_message_is_human_readable() -> None:
    assert _humanize_readiness_message("document has coverage gaps") == (
        "Есть пробелы в покрытии требований вакансии"
    )
