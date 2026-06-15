from app.services.vacancy_fit_narrative_service import VacancyFitNarrativeService


def test_vacancy_fit_narrative_normalizes_missing_keywords() -> None:
    narrative = VacancyFitNarrativeService().build(
        matched_keywords=["Ведение проектной документации"],
        missing_keywords=[
            "Настройка BIM-процессов и координация проектирования",
            "Взаимодействие с экспертизой и прохождение экспертизы",
            "Команду архитекторов, инженеров, BIM-специалистов и управленцев",
            "Проектная документация Проектный менеджмент Ведение проектной документации",
            "Работу в проектной BIM-компании с реальными задачами и растущим объёмом проектов",
        ],
        vacancy_evidence_alignment=[],
        selected_achievements=[],
        selected_skills=[],
    )

    assert [
        item["label"]
        for item in narrative["critical_gaps"]
    ] == [
        "BIM-процессы",
        "взаимодействие с экспертизой",
        "управление межфункциональной проектной командой",
        "опыт BIM-проектирования",
    ]

    assert [
        item["label"]
        for item in narrative["matched_strengths"]
    ] == ["Ведение проектной документации"]
