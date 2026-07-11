from app.services.evidence_strength_ranker import EvidenceStrengthRanker


def test_evidence_strength_ranker_prefers_persuasive_relevant_achievement() -> None:
    ranker = EvidenceStrengthRanker()

    achievements = [
        {
            "title": "Подготовила более 250 договоров",
            "fact_status": "confirmed",
        },
        {
            "title": "Запустила 8 проектов в срок",
            "fact_status": "confirmed",
        },
    ]

    ranked = ranker.rank_achievements(
        achievements,
        vacancy_title="Руководитель проектов",
        selected_skills=["Project Management", "Бюджетирование"],
    )

    assert ranked[0]["title"] == "Запустила 8 проектов в срок"
    assert ranked[1]["title"] == "Подготовила более 250 договоров"


def test_evidence_strength_ranker_scores_components_separately() -> None:
    ranker = EvidenceStrengthRanker()

    score = ranker.score_achievement(
        {
            "title": "Снизила количество просроченных задач на 40%",
            "fact_status": "user_provided",
        },
        context="Руководитель проектов Jira Scrum сроки бюджет",
    )

    assert score.total >= 35
    assert score.evidence_strength >= 20
    assert score.diversity == 10
    assert "action" in score.reasons
    assert "metric" in score.reasons


def test_evidence_strength_ranker_filters_weak_claims_without_mutating() -> None:
    ranker = EvidenceStrengthRanker()
    achievements = [
        {"title": "Создал документы"},
        {
            "title": "Оптимизировал складские остатки на 25%",
            "fact_status": "confirmed",
        },
    ]
    original = [dict(item) for item in achievements]

    ranked = ranker.rank_achievements(
        achievements,
        vacancy_title="Руководитель склада",
        min_score=25,
    )

    assert ranked == [
        {
            "title": "Оптимизировал складские остатки на 25%",
            "fact_status": "confirmed",
        }
    ]
    assert achievements == original
