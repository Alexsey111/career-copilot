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
        item["classification"]
        for item in narrative["critical_gaps"]
    ] == [
        "competency",
        "competency",
        "competency",
        "competency",
    ]

    assert [
        item["label"]
        for item in narrative["matched_strengths"]
    ] == ["Ведение проектной документации"]


def test_vacancy_fit_narrative_humanizes_angle_labels() -> None:
    narrative = VacancyFitNarrativeService().build(
        matched_keywords=["Подготовка договоров", "Работа в 1С:Бухгалтерия"],
        missing_keywords=[],
        vacancy_evidence_alignment=[],
        selected_achievements=[],
        selected_skills=[],
    )

    assert "подготовки договоров" in narrative["resume_angle"]
    assert "работы в 1С:Бухгалтерия" in narrative["resume_angle"]


def test_vacancy_fit_narrative_filters_soft_skills_from_critical_gaps() -> None:
    """Soft skills не должны попадать в critical_gaps."""
    narrative = VacancyFitNarrativeService().build(
        matched_keywords=["Python", "FastAPI"],
        missing_keywords=[
            "Ответственность",
            "Внимательность",
            "Коммуникабельность",
            "Исполнительность",
            "Аккуратность",
            "Docker",
            "PostgreSQL",
        ],
        vacancy_evidence_alignment=[],
        selected_achievements=[],
        selected_skills=[],
    )

    gap_labels = [item["label"].lower() for item in narrative["critical_gaps"]]
    assert "ответственность" not in gap_labels
    assert "внимательность" not in gap_labels
    assert "коммуникабельность" not in gap_labels
    assert "исполнительность" not in gap_labels
    assert "аккуратность" not in gap_labels
    assert "docker" in gap_labels
    assert "postgresql" in gap_labels


def test_vacancy_fit_narrative_filters_soft_skills_from_resume_angle() -> None:
    """Soft skills не должны попадать в resume_angle как gaps."""
    narrative = VacancyFitNarrativeService().build(
        matched_keywords=["Python"],
        missing_keywords=[
            "Ответственность",
            "Внимательность",
            "Docker",
        ],
        vacancy_evidence_alignment=[],
        selected_achievements=[],
        selected_skills=[],
    )

    resume_angle = narrative["resume_angle"].lower()
    assert "ответственность" not in resume_angle
    assert "внимательность" not in resume_angle
    assert "docker" in resume_angle or "doker" in resume_angle


def test_vacancy_fit_narrative_filters_soft_skills_from_cover_letter_angle() -> None:
    """Soft skills не должны попадать в cover_letter_angle как gaps."""
    narrative = VacancyFitNarrativeService().build(
        matched_keywords=["Python"],
        missing_keywords=[
            "Аккуратность",
            "Исполнительность",
            "Kubernetes",
        ],
        vacancy_evidence_alignment=[],
        selected_achievements=[],
        selected_skills=[],
    )

    cover_letter_angle = narrative["cover_letter_angle"].lower()
    assert "аккуратность" not in cover_letter_angle
    assert "исполнительность" not in cover_letter_angle
