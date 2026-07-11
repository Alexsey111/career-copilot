from app.services.semantic_summary_ranker import SemanticSummaryRanker


def test_semantic_summary_ranker_prioritizes_project_management_responsibilities() -> None:
    ranker = SemanticSummaryRanker()

    ranked = ranker.rank_focus_phrases(
        phrases=[
            "Ведение документации",
            "Планирование сроков и бюджета",
            "Управление IT-проектами",
            "Координация команды 12 человек",
        ],
        vacancy_title="Руководитель проектов",
        selected_skills=["Jira", "Scrum"],
        selected_achievements=[],
    )

    assert ranked[:3] == [
        "Управление IT-проектами",
        "Координация команды 12 человек",
        "Планирование сроков и бюджета",
    ]


def test_semantic_summary_ranker_uses_top_alignment_confidence() -> None:
    ranker = SemanticSummaryRanker()

    ranked = ranker.rank_top_alignment_evidence(
        evidence_items=[
            {
                "requirement": "Documentation",
                "summary_phrase": "ведение документации",
                "confidence": "medium",
            },
            {
                "requirement": "Project management",
                "summary_phrase": "управление IT-проектами",
                "confidence": "high",
            },
        ],
        vacancy_title="Руководитель проектов",
    )

    assert ranked[0]["summary_phrase"] == "управление IT-проектами"


def test_semantic_summary_ranker_ranks_skills_for_summary_fallback() -> None:
    ranker = SemanticSummaryRanker()

    ranked = ranker.rank_skills(
        skills=["Confluence", "Jira", "Бюджетирование", "Управление проектами"],
        vacancy_title="Руководитель проектов",
        selected_achievements=[],
    )

    assert ranked[0] == "Управление проектами"
    assert "Бюджетирование" in ranked[:3]


def test_semantic_summary_ranker_filters_weak_summary_achievements() -> None:
    ranker = SemanticSummaryRanker()

    strong = ranker.strong_summary_achievements(
        [
            {"title": "ИИ-система мониторинга безопасности"},
            {"title": "Снизила количество просроченных задач на 40%"},
        ]
    )

    assert strong == [{"title": "Снизила количество просроченных задач на 40%"}]
