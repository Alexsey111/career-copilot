# tests/evals/test_achievement_retrieval.py

from app.services.achievement_retrieval_service import AchievementRetrievalService


class TestAchievementRetrievalService:

    def test_score_achievement_against_requirement_returns_nonzero_for_relevant_achievement(self) -> None:
        service = AchievementRetrievalService()
        achievement = {
            "title": "Разработал ETL pipeline для анализа данных",
            "situation": "Собирал данные из нескольких источников",
            "task": "Нужно было объединить данные",
            "action": "Настроил процессы загрузки и трансформации",
            "result": "Объём данных вырос в 5 раз",
            "metric_text": "5x",
        }
        score = service.score_achievement_against_requirement(
            achievement=achievement,
            requirement_text="опыт разработки ETL для анализа данных",
        )

        assert score > 0

    def test_select_relevant_achievements_excludes_irrelevant_items(self) -> None:
        service = AchievementRetrievalService()
        achievements = [
            {
                "id": "a1",
                "title": "Поддерживал сотрудникую базу данных",
                "fact_status": "confirmed",
                "evidence_note": "Ссылка на GitHub",
            },
            {
                "id": "a2",
                "title": "Разработал ETL pipeline для анализа данных",
                "fact_status": "confirmed",
                "evidence_note": "Документация проекта",
            },
        ]
        requirements = [
            {"text": "Разработка ETL pipeline для аналитики", "scope": "must_have"},
        ]

        selected, trace = service.select_relevant_achievements(
            achievements=achievements,
            requirements=requirements,
        )

        assert len(selected) == 1
        assert selected[0].id == "a2"
        assert trace.selected_achievement_ids == ["a2"]
        assert trace.retrieval_trace[0]["why_selected"].startswith(
            "Achievement подтверждён"
        )

    def test_select_relevant_achievements_rejects_unsupported_claims(self) -> None:
        service = AchievementRetrievalService()
        achievements = [
            {
                "id": "a1",
                "title": "Разработал ETL pipeline для анализа данных",
                "fact_status": "needs_confirmation",
                "evidence_note": "Документация проекта",
            },
        ]
        requirements = [
            {"text": "Разработка ETL pipeline для аналитики", "scope": "must_have"},
        ]

        selected, trace = service.select_relevant_achievements(
            achievements=achievements,
            requirements=requirements,
        )

        assert selected == []
        assert trace.selected_achievement_ids == []
        assert trace.retrieval_trace == []

    def test_select_relevant_achievements_rejects_empty_evidence_mapping(self) -> None:
        service = AchievementRetrievalService()
        achievements = [
            {
                "id": "a1",
                "title": "Разработал ETL pipeline для анализа данных",
                "fact_status": "confirmed",
                "evidence_note": "",
            },
        ]
        requirements = [
            {"text": "Разработка ETL pipeline для аналитики", "scope": "must_have"},
        ]

        selected, trace = service.select_relevant_achievements(
            achievements=achievements,
            requirements=requirements,
        )

        assert selected == []
        assert trace.selected_achievement_ids == []
        assert trace.retrieval_trace == []
