from pathlib import Path
import sys

STREAMLIT_ROOT = Path(__file__).resolve().parents[1] / "frontend" / "streamlit"
if str(STREAMLIT_ROOT) not in sys.path:
    sys.path.insert(0, str(STREAMLIT_ROOT))

from components.document_review_workspace import (  # type: ignore import-not-found
    _achievement_missing_labels,
    _confidence_item_label,
    _format_roadmap_score,
    _humanize_readiness_message,
    _parse_achievement_diagnostics,
    _score_breakdown_caption,
    _risk_item_label,
    _vacancy_gap_priority_label,
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
        "Оценка соответствия вакансии сейчас низкая, потому что структурное покрытие профиля пока ограничено"
    )
    assert _risk_item_label(
        "missing or weakly represented vacancy keywords: FastAPI"
    ) == "Ключевые слова вакансии представлены слабо или отсутствуют"
    assert _risk_item_label(
        "resume draft is ATS-safe plaintext-oriented and not final formatted output"
    ) == (
        "Черновик резюме пока только в текстовом виде, без финального форматирования, и безопасен для ATS"
    )


def test_readiness_message_is_human_readable() -> None:
    assert _humanize_readiness_message("document has coverage gaps") == (
        "Есть пробелы в покрытии требований вакансии"
    )


def test_parse_achievement_diagnostics() -> None:
    diagnostics = _parse_achievement_diagnostics(
        "Диагностика достижений: всего 4, без действия 1, без результата 4, без метрики 3."
    )

    assert diagnostics == {
        "total": 4,
        "without_action": 1,
        "without_result": 4,
        "without_metric": 3,
    }


def test_achievement_missing_labels_are_human_readable() -> None:
    assert _achievement_missing_labels(["action", "result", "metric"]) == [
        "нет действия",
        "нет результата",
        "нет метрики",
    ]


def test_vacancy_gap_priority_label_is_human_readable() -> None:
    assert _vacancy_gap_priority_label("high") == "Высокий риск"
    assert _vacancy_gap_priority_label("medium") == "Средний риск"
    assert _vacancy_gap_priority_label("low") == "Низкий риск"
    assert _vacancy_gap_priority_label("") == "Риск не определён"


def test_score_breakdown_caption_is_ranked_by_relative_gap() -> None:
    assert _score_breakdown_caption(0, 25) == "🔥 Основная причина низкой оценки (+25)"
    assert _score_breakdown_caption(0, 8) == "🔥 Самый большой резерв улучшения (+8)"
    assert _score_breakdown_caption(1, 8) == "⚡ Один из основных резервов (+8)"
    assert _score_breakdown_caption(2, 3) == "⚡ Дополнительный резерв (+3)"
    assert _score_breakdown_caption(3, 0) == "✓ Почти оптимально"


def test_format_roadmap_score_uses_clean_integer_display() -> None:
    assert _format_roadmap_score(67) == "67"
    assert _format_roadmap_score(91.6) == "92"
    assert _format_roadmap_score(None) == "—"
