from pathlib import Path
import sys

STREAMLIT_ROOT = Path(__file__).resolve().parents[1] / "frontend" / "streamlit"
if str(STREAMLIT_ROOT) not in sys.path:
    sys.path.insert(0, str(STREAMLIT_ROOT))

from components.interview_prep_workspace import (  # type: ignore
    _humanize_evidence_fact_status,
    _humanize_evidence_source,
    _sanitize_evidence_text,
)


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
