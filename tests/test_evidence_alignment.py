from app.domain.evidence_alignment import polish_summary_evidence_phrase


def test_polish_summary_evidence_phrase_compacts_project_reporting() -> None:
    assert (
        polish_summary_evidence_phrase("систему проектной отчётности")
        == "внедрения системы проектной отчётности"
    )
