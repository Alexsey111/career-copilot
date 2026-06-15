from app.services.vacancy_fit_context_service import VacancyFitContextService


def test_vacancy_fit_context_builds_shared_alignment_and_narrative() -> None:
    service = VacancyFitContextService()

    context = service.build(
        matched_keywords=["Python", "Docker"],
        missing_keywords=["FastAPI", "BIM-процессы"],
        selected_skills=["Python", "Docker"],
        evidence_snippets=[
            {
                "id": "e-1",
                "title": "Python backend service",
                "snippet_text": "Built Python API service for backend workflow",
                "skills": ["Python", "FastAPI"],
                "fact_status": "confirmed",
                "source_type": "resume",
            }
        ],
        selected_achievements=[
            {
                "id": "a-1",
                "title": "Built backend service",
                "fact_status": "confirmed",
            }
        ],
    )

    assert set(context) == {"vacancy_evidence_alignment", "vacancy_fit_narrative"}

    vacancy_evidence_alignment = context["vacancy_evidence_alignment"]
    vacancy_fit_narrative = context["vacancy_fit_narrative"]

    assert vacancy_evidence_alignment
    assert vacancy_fit_narrative["matched_strengths"]
    assert vacancy_fit_narrative["critical_gaps"]
    assert any(
        item["label"].lower() == "python"
        for item in vacancy_fit_narrative["matched_strengths"]
    )


def test_shared_context_excludes_matched_label_from_critical_gaps() -> None:
    context = VacancyFitContextService().build(
        matched_keywords=["ведение проектной документации"],
        missing_keywords=["ведение проектной документации", "BIM-процессы"],
        selected_achievements=[],
        selected_skills=[],
        evidence_snippets=[],
    )

    narrative = context["vacancy_fit_narrative"]

    assert [item["label"] for item in narrative["matched_strengths"]] == [
        "ведение проектной документации"
    ]
    assert "ведение проектной документации" not in [
        item["label"] for item in narrative["critical_gaps"]
    ]
