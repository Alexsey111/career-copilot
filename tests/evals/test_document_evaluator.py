# tests/evals/test_document_evaluator.py

from __future__ import annotations

import pytest

from app.domain.trace_models import AIAuditMetadata, GenerationTrace
from app.services.document_evaluator import (
    DocumentEvaluator,
    evaluate_document,
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
