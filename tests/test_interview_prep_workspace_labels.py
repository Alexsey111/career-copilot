from pathlib import Path
import sys

STREAMLIT_ROOT = Path(__file__).resolve().parents[1] / "frontend" / "streamlit"
if str(STREAMLIT_ROOT) not in sys.path:
    sys.path.insert(0, str(STREAMLIT_ROOT))

from components.interview_prep_formatters import (  # type: ignore
    _humanize_evidence_fact_status,
    _humanize_evidence_source,
    _humanize_reason,
    _normalize_competency_label,
)
from components.interview_prep_helpers import _sanitize_evidence_text  # type: ignore


def test_sanitize_evidence_text_removes_internal_provenance_marker() -> None:
    assert _sanitize_evidence_text(
        "Сократила сроки подготовки макетов на 30% Extracted as a"
    ) == "Сократила сроки подготовки макетов на 30%"

    assert _sanitize_evidence_text(
        "Участвовала в ребрендинге normalized contribution signal"
    ) == "Участвовала в ребрендинге"


def test_humanize_evidence_source_and_status_hide_internal_values() -> None:
    assert _humanize_evidence_source("structured_resume_extraction_v2") == (
        "Импортировано из резюме"
    )
    assert _humanize_evidence_fact_status("user_provided") == (
        "Подтверждено кандидатом"
    )


def test_normalize_competency_label_uses_dictionary_form() -> None:
    assert _normalize_competency_label("коммуникацию") == "коммуникация"
    assert _normalize_competency_label("Коммуникацией") == "Коммуникация"


def test_humanize_reason_rewrites_legacy_domain_context_text() -> None:
    assert _humanize_reason(
        "Совпадает с доменным контекстом · Факт подтверждён"
    ) == "Связано с предметной областью вакансии"
