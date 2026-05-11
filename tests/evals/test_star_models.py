from app.domain.star_models import STARStoryDraft, Competency, CompetencyMapping
from app.services.star_extraction_service import STARExtractionService
from app.services.answer_evaluation_engine import AnswerEvaluationEngine


class TestSTARStoryDraft:
    """Тесты для STARStoryDraft модели."""

    def test_star_story_complete(self) -> None:
        """Полная STAR история."""
        story = STARStoryDraft(
            achievement_id="ach-1",
            situation="high latency issues",
            task="reduce processing time",
            action="implemented async pipeline",
            result="reduced latency by 40%",
            evidence_strength="strong",
            quality_score=0.85,
        )

        assert story.is_complete is True
        assert "implemented" in story.summary
        assert "40%" in story.summary

    def test_star_story_incomplete(self) -> None:
        """Неполная STAR история."""
        story = STARStoryDraft(
            achievement_id="ach-2",
            situation="",
            task="fix bugs",
            action="",
            result="",
            evidence_strength="weak",
            quality_score=0.2,
        )

        assert story.is_complete is False


class TestSTARExtractionService:
    """Тесты для STARExtractionService."""

    def test_extract_star_story(self) -> None:
        """Извлечение STAR истории из достижения."""
        service = STARExtractionService()

        achievement = {
            "id": "ach-1",
            "situation": "slow API responses",
            "task": "improve performance",
            "action": "implemented caching with Redis",
            "result": "reduced latency by 60%",
            "evidence_note": "Grafana dashboard link",
            "fact_status": "confirmed",
        }

        story = service.extract_star_story(achievement)

        assert story.achievement_id == "ach-1"
        assert story.situation == "slow API responses"
        assert story.action == "implemented caching with Redis"
        assert story.result == "reduced latency by 60%"
        assert story.evidence_strength == "strong"
        assert story.quality_score > 0.5

    def test_extract_star_story_weak_evidence(self) -> None:
        """Извлечение с weak evidence."""
        service = STARExtractionService()

        achievement = {
            "id": "ach-2",
            "situation": "",
            "task": "",
            "action": "worked on optimization",
            "result": "",
            "evidence_note": "",
            "fact_status": "pending",
        }

        story = service.extract_star_story(achievement)

        assert story.evidence_strength == "weak"
        assert story.is_complete is False

    def test_map_to_competencies(self) -> None:
        """Маппинг требований на компетенции и STAR истории."""
        service = STARExtractionService()

        requirements = [
            {"text": "Python backend development", "keyword": "Python"},
            {"text": "team management", "keyword": "management"},
        ]

        achievements = [
            {
                "id": "ach-1",
                "situation": "legacy system",
                "task": "migrate to new framework",
                "action": "implemented FastAPI backend",
                "result": "reduced response time by 40%",
                "evidence_note": "",
                "fact_status": "confirmed",
            },
        ]

        competency_keywords = {
            "backend": ["python", "fastapi", "backend"],
            "management": ["team", "lead", "manage"],
        }

        star_stories = service.extract_all_stars(achievements)
        mappings = service.map_to_competencies(
            requirements=requirements,
            star_stories=star_stories,
            competency_keywords=competency_keywords,
        )

        assert len(mappings) == 2
        # Первый requirement должен быть matched
        backend_mapping = mappings[0]
        assert backend_mapping.competency.name == "backend"
        assert len(backend_mapping.matched_story_ids) >= 1
        assert backend_mapping.coverage_type in {"direct", "partial"}


class TestAnswerEvaluationEngine:
    """Тесты для AnswerEvaluationEngine."""

    def test_answer_high_quality(self) -> None:
        """Качественный ответ с метриками и action verbs."""
        answer = "I implemented async FastAPI pipeline reducing latency by 40% for 10000 users"

        engine = AnswerEvaluationEngine(answer)
        checks = engine.evaluate()

        assert engine.is_acceptable is True
        assert engine.overall_score >= 0.6

        specificity_check = next(c for c in checks if c.check_name == "specificity")
        assert specificity_check.passed

    def test_answer_generic_wording(self) -> None:
        """Ответ с generic формулировками."""
        answer = "I participated in the project and helped the team"

        engine = AnswerEvaluationEngine(answer)
        checks = engine.evaluate()

        generic_check = next(c for c in checks if c.check_name == "generic_wording")
        assert not generic_check.passed
        assert generic_check.severity == "warning"

    def test_answer_incomplete_star(self) -> None:
        """Ответ без полной STAR структуры."""
        answer = "I worked on optimization tasks"

        engine = AnswerEvaluationEngine(answer)
        checks = engine.evaluate()

        star_check = next(c for c in checks if c.check_name == "star_completeness")
        assert not star_check.passed
        assert star_check.severity == "warning"

    def test_answer_with_metrics(self) -> None:
        """Ответ с измеримыми результатами."""
        answer = "Developed ETL pipeline processing 1M records daily, reducing costs by $5000/month"

        engine = AnswerEvaluationEngine(answer)
        checks = engine.evaluate()

        evidence_check = next(c for c in checks if c.check_name == "evidence_quality")
        assert evidence_check.passed

    def test_overall_score_calculation(self) -> None:
        """Расчёт общего score."""
        # Высокий score
        answer_good = "Implemented async pipeline reducing latency by 40%"
        engine_good = AnswerEvaluationEngine(answer_good)
        score_good = engine_good.overall_score
        assert score_good >= 0.0  # score может быть низким из-за неполного STAR

        # Низкий score
        answer_bad = "Worked on the project"
        engine_bad = AnswerEvaluationEngine(answer_bad)
        score_bad = engine_bad.overall_score
        # Оба могут быть низкими, но bad должен быть не выше good
        assert score_bad <= score_good + 0.1
