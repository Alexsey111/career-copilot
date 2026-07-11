# tests/evals/test_document_evaluator.py

from __future__ import annotations

import pytest

from app.domain.trace_models import AIAuditMetadata, GenerationTrace
from app.services.document_evaluator import (
    DocumentEvaluator,
    evaluate_document,
    extract_baseline_metrics,
)


class TestNoHallucinatedMetrics:
    """Проверка на выдуманные метрики."""

    def test_pass_no_metrics(self) -> None:
        content = {
            "sections": {
                "selected_achievements": [
                    {
                        "title": "Optimized API",
                        "result": "Improved response time",
                        "metric_text": "",
                        "fact_status": "confirmed",
                    }
                ]
            }
        }

        evaluator = DocumentEvaluator(original_content=None, generated_content=content)
        report = evaluator.evaluate()

        assert any(
            check.check_name == "no_hallucinated_metrics" and check.passed
            for check in report.checks
        )

    def test_fail_unconfirmed_metrics(self) -> None:
        content = {
            "sections": {
                "selected_achievements": [
                    {
                        "title": "Optimized API",
                        "result": "Improved performance by 50%",
                        "metric_text": "50% faster",
                        "fact_status": "needs_confirmation",
                    }
                ]
            }
        }

        evaluator = DocumentEvaluator(original_content=None, generated_content=content)
        report = evaluator.evaluate()

        assert any(
            check.check_name == "no_hallucinated_metrics"
            and not check.passed
            and check.severity == "critical"
            for check in report.checks
        )

    def test_pass_confirmed_metrics(self) -> None:
        content = {
            "sections": {
                "selected_achievements": [
                    {
                        "title": "Optimized API",
                        "result": "Improved performance by 50%",
                        "metric_text": "50% faster",
                        "fact_status": "confirmed",
                    }
                ]
            }
        }

        evaluator = DocumentEvaluator(original_content=None, generated_content=content)
        report = evaluator.evaluate()

        assert any(
            check.check_name == "no_hallucinated_metrics" and check.passed
            for check in report.checks
        )


class TestNoFabricatedExperience:
    """Проверка на выдуманный опыт."""

    def test_pass_same_companies(self) -> None:
        original = {
            "experience": [
                {"company": "TechCorp", "role": "Backend Developer"},
            ]
        }
        content = {
            "sections": {
                "experience": [
                    {"company": "TechCorp", "role": "Senior Backend Developer"},
                ]
            }
        }

        evaluator = DocumentEvaluator(
            original_content=original, generated_content=content
        )
        report = evaluator.evaluate()

        assert any(
            check.check_name == "no_fabricated_experience" and check.passed
            for check in report.checks
        )

    def test_fail_new_company(self) -> None:
        original = {
            "experience": [
                {"company": "TechCorp", "role": "Backend Developer"},
            ]
        }
        content = {
            "sections": {
                "experience": [
                    {"company": "UnknownCorp", "role": "Lead Developer"},
                ]
            }
        }

        evaluator = DocumentEvaluator(
            original_content=original, generated_content=content
        )
        report = evaluator.evaluate()

        assert any(
            check.check_name == "no_fabricated_experience"
            and not check.passed
            and check.severity == "warning"
            for check in report.checks
        )


class TestNoKeywordLoss:
    """Проверка на потерю ключевых слов."""

    def test_pass_all_keywords_preserved(self) -> None:
        original = {"matched_keywords": ["Python", "FastAPI", "SQLAlchemy"]}
        content = {
            "sections": {
                "matched_keywords": ["Python", "FastAPI", "SQLAlchemy"],
            }
        }

        evaluator = DocumentEvaluator(
            original_content=original, generated_content=content
        )
        report = evaluator.evaluate()

        assert any(
            check.check_name == "no_keyword_loss" and check.passed
            for check in report.checks
        )

    def test_fail_some_keywords_lost(self) -> None:
        original = {"matched_keywords": ["Python", "FastAPI", "SQLAlchemy", "Redis"]}
        content = {
            "sections": {
                "matched_keywords": ["Python", "FastAPI"],
            }
        }

        evaluator = DocumentEvaluator(
            original_content=original, generated_content=content
        )
        report = evaluator.evaluate()

        assert any(
            check.check_name == "no_keyword_loss"
            and not check.passed
            and check.severity == "warning"
            for check in report.checks
        )


class TestNoUnsafeEnhancement:
    """Проверка на unsafe AI enhancement."""

    def test_pass_safety_checks_passed(self) -> None:
        content = {
            "meta": {
                "ai_metadata": {
                    "safety_checks_passed": True,
                    "model": "gigachat",
                    "temperature": 0.2,
                }
            }
        }

        evaluator = DocumentEvaluator(original_content=None, generated_content=content)
        report = evaluator.evaluate()

        assert any(
            check.check_name == "no_unsafe_enhancement" and check.passed
            for check in report.checks
        )

    def test_fail_safety_checks_failed(self) -> None:
        content = {
            "meta": {
                "ai_metadata": {
                    "safety_checks_passed": False,
                    "model": "gigachat",
                    "temperature": 0.7,
                }
            }
        }

        evaluator = DocumentEvaluator(original_content=None, generated_content=content)
        report = evaluator.evaluate()

        assert any(
            check.check_name == "no_unsafe_enhancement"
            and not check.passed
            and check.severity == "critical"
            for check in report.checks
        )


class TestNoEmptyRendering:
    """Проверка на пустой рендеринг."""

    def test_pass_non_empty_rendering(self) -> None:
        content = {
            "rendered_text": "Иван Иванов\nBackend Developer\n\nЦЕЛЕВАЯ ПОЗИЦИЯ\nPython Developer..."
        }

        evaluator = DocumentEvaluator(original_content=None, generated_content=content)
        report = evaluator.evaluate()

        assert any(
            check.check_name == "no_empty_rendering" and check.passed
            for check in report.checks
        )

    def test_fail_empty_rendering(self) -> None:
        content = {
            "rendered_text": ""
        }

        evaluator = DocumentEvaluator(original_content=None, generated_content=content)
        report = evaluator.evaluate()

        assert any(
            check.check_name == "no_empty_rendering"
            and not check.passed
            and check.severity == "critical"
            for check in report.checks
        )

    def test_fail_too_short_rendering(self) -> None:
        content = {
            "rendered_text": "Too short"
        }

        evaluator = DocumentEvaluator(original_content=None, generated_content=content)
        report = evaluator.evaluate()

        assert any(
            check.check_name == "no_empty_rendering"
            and not check.passed
            for check in report.checks
        )


class TestATSKeywordPreservation:
    """Проверка на сохранение ATS-ключевых слов."""

    def test_pass_all_skills_preserved(self) -> None:
        original = {
            "sections": {
                "skills": ["Python", "FastAPI", "PostgreSQL", "Docker"]
            }
        }
        content = {
            "sections": {
                "skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
            }
        }

        evaluator = DocumentEvaluator(
            original_content=original, generated_content=content
        )
        report = evaluator.evaluate()

        assert any(
            check.check_name == "ats_keyword_preservation" and check.passed
            for check in report.checks
        )

    def test_fail_some_skills_lost(self) -> None:
        original = {
            "sections": {
                "skills": ["Python", "FastAPI", "PostgreSQL", "Redis"]
            }
        }
        content = {
            "sections": {
                "skills": ["Python", "FastAPI"],
            }
        }

        evaluator = DocumentEvaluator(
            original_content=original, generated_content=content
        )
        report = evaluator.evaluate()

        assert any(
            check.check_name == "ats_keyword_preservation"
            and not check.passed
            for check in report.checks
        )


class TestDocumentEvaluationReport:
    """Проверка DocumentEvaluationReport."""

    def test_is_safe_when_no_critical_failures(self) -> None:
        content = {
            "sections": {
                "selected_achievements": [
                    {
                        "title": "Test",
                        "result": "Improved performance",
                        "fact_status": "confirmed",
                    }
                ],
                "matched_keywords": ["Python"],
            },
            "rendered_text": "x" * 100,
        }

        report = evaluate_document(
            original_content=None,
            generated_content=content,
        )

        assert report.is_safe is True

    def test_is_unsafe_with_critical_failure(self) -> None:
        content = {
            "sections": {
                "selected_achievements": [
                    {
                        "title": "Test",
                        "result": "Improved by 50%",
                        "fact_status": "needs_confirmation",
                    }
                ],
            },
            "rendered_text": "x" * 100,
        }

        report = evaluate_document(
            original_content=None,
            generated_content=content,
        )

        assert report.is_safe is False

    def test_trace_and_ai_metadata_attached(self) -> None:
        content = {
            "sections": {
                "selected_achievements": [
                    {
                        "title": "Test",
                        "fact_status": "confirmed",
                    }
                ],
            },
            "rendered_text": "x" * 100,
        }

        trace = GenerationTrace(
            selected_achievement_ids=["uuid-1"],
            matched_keywords=["Python"],
            builder_version="v1",
        )

        ai_metadata = AIAuditMetadata(
            model="gigachat",
            prompt_version="v2",
            temperature=0.2,
        )

        report = evaluate_document(
            original_content=None,
            generated_content=content,
            trace=trace,
            ai_metadata=ai_metadata,
        )

        assert report.trace is not None
        assert report.trace.builder_version == "v1"
        assert report.ai_metadata is not None
        assert report.ai_metadata.model == "gigachat"


class TestNoHallucinatedNarrativeMetrics:
    """Проверка на выдуманные метрики в AI-enhanced тексте (rendered_text/fit_summary)."""

    def test_metric_not_in_baseline_is_critical(self) -> None:
        original = {"baseline_metrics": {("30", "%")}}
        content = {
            "sections": {"selected_achievements": [], "matched_keywords": []},
            "rendered_text": "Увеличил конверсию на 120% за квартал. " + "x" * 100,
        }

        evaluator = DocumentEvaluator(
            original_content=original, generated_content=content
        )
        report = evaluator.evaluate()

        check = next(
            c for c in report.checks
            if c.check_name == "no_hallucinated_narrative_metrics"
        )
        assert not check.passed
        assert check.severity == "critical"
        assert report.has_hallucinated_metrics is True
        assert report.is_safe is False

    def test_metric_in_baseline_passes(self) -> None:
        original = {"baseline_metrics": {("30", "%")}}
        content = {
            "sections": {"selected_achievements": [], "matched_keywords": []},
            "rendered_text": "Рост на 30% подтверждён. " + "x" * 100,
        }

        evaluator = DocumentEvaluator(
            original_content=original, generated_content=content
        )
        report = evaluator.evaluate()

        check = next(
            c for c in report.checks
            if c.check_name == "no_hallucinated_narrative_metrics"
        )
        assert check.passed
        assert report.has_hallucinated_metrics is False

    def test_empty_baseline_skips_narrative_check(self) -> None:
        original = {"baseline_metrics": set()}
        content = {
            "sections": {"selected_achievements": [], "matched_keywords": []},
            "rendered_text": "Увеличил на 120%. " + "x" * 100,
        }

        evaluator = DocumentEvaluator(
            original_content=original, generated_content=content
        )
        report = evaluator.evaluate()

        check = next(
            c for c in report.checks
            if c.check_name == "no_hallucinated_narrative_metrics"
        )
        assert check.passed
        assert check.severity == "info"
        assert report.is_safe is True

    def test_fit_summary_string_is_scanned(self) -> None:
        original = {"baseline_metrics": {("30", "%")}}
        content = {
            "sections": {
                "selected_achievements": [],
                "matched_keywords": [],
                "fit_summary": "Сократил расходы на 75%.",
            },
            "rendered_text": "x" * 100,
        }

        evaluator = DocumentEvaluator(
            original_content=original, generated_content=content
        )
        report = evaluator.evaluate()

        check = next(
            c for c in report.checks
            if c.check_name == "no_hallucinated_narrative_metrics"
        )
        assert not check.passed
        assert check.severity == "critical"

    def test_fit_summary_dict_is_ignored(self) -> None:
        original = {"baseline_metrics": {("30", "%")}}
        content = {
            "sections": {
                "selected_achievements": [],
                "matched_keywords": [],
                "fit_summary": {"match_score": 0.8, "target_role": "Backend"},
            },
            "rendered_text": "Без метрик. " + "x" * 100,
        }

        evaluator = DocumentEvaluator(
            original_content=original, generated_content=content
        )
        report = evaluator.evaluate()

        check = next(
            c for c in report.checks
            if c.check_name == "no_hallucinated_narrative_metrics"
        )
        assert check.passed


class TestExtractBaselineMetrics:
    """Проверка построения baseline из подтверждённых достижений/опыта."""

    def test_confirmed_achievement_metrics_included(self) -> None:
        achievements = [
            {"result": "Рост на 30%", "metric_text": "30%", "fact_status": "confirmed"},
            {"result": "Снизил на 5%", "metric_text": "", "fact_status": "user_provided"},
        ]
        baseline = extract_baseline_metrics(achievements)
        assert ("30", "%") in baseline
        assert ("5", "%") in baseline

    def test_unconfirmed_achievement_metrics_excluded(self) -> None:
        achievements = [
            {"result": "Рост на 999%", "metric_text": "", "fact_status": "needs_confirmation"},
        ]
        baseline = extract_baseline_metrics(achievements)
        assert ("999", "%") not in baseline
        assert baseline == set()

    def test_experience_description_metrics_included(self) -> None:
        achievements = [{"result": "", "metric_text": "", "fact_status": "confirmed"}]
        experience = [{"description_raw": "Внедрил CI/CD, ускорил в 4 раза сборку"}]
        baseline = extract_baseline_metrics(achievements, experience)
        assert ("4", "раз") in baseline
