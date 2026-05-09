# tests/evals/test_mandatory_review.py

from __future__ import annotations

import pytest

from app.domain.trace_models import (
    DocumentEvaluationReport,
    DeterministicCheckResult,
)
from app.services.document_review_service import DocumentReviewService


class TestMandatoryReviewLogic:
    """Тесты для mandatory review на основе eval failures."""

    def test_no_review_required_when_all_checks_pass(self) -> None:
        report = DocumentEvaluationReport(
            checks=[
                DeterministicCheckResult(
                    passed=True,
                    check_name="no_hallucinated_metrics",
                    message="OK",
                    severity="info",
                ),
                DeterministicCheckResult(
                    passed=True,
                    check_name="no_keyword_loss",
                    message="OK",
                    severity="info",
                ),
            ]
        )

        service = DocumentReviewService()
        requires_review, reason = service.evaluate_review_requirement(report)

        assert requires_review is False
        assert reason == "No mandatory review required"

    def test_review_required_when_critical_failure(self) -> None:
        report = DocumentEvaluationReport(
            checks=[
                DeterministicCheckResult(
                    passed=False,
                    check_name="no_hallucinated_metrics",
                    message="Unconfirmed metric: 50% increase",
                    severity="critical",
                ),
            ]
        )

        service = DocumentReviewService()
        requires_review, reason = service.evaluate_review_requirement(report)

        assert requires_review is True
        assert "Critical failures detected" in reason
        assert "Unconfirmed metric" in reason

    def test_review_required_when_multiple_warnings(self) -> None:
        report = DocumentEvaluationReport(
            checks=[
                DeterministicCheckResult(
                    passed=False,
                    check_name="no_keyword_loss",
                    message="Lost: Redis",
                    severity="warning",
                ),
                DeterministicCheckResult(
                    passed=False,
                    check_name="ats_keyword_preservation",
                    message="Lost: Docker",
                    severity="warning",
                ),
                DeterministicCheckResult(
                    passed=False,
                    check_name="no_fabricated_experience",
                    message="New company: UnknownCorp",
                    severity="warning",
                ),
            ]
        )

        service = DocumentReviewService()
        requires_review, reason = service.evaluate_review_requirement(report)

        assert requires_review is True
        assert "Multiple warnings detected" in reason
        assert "3" in reason

    def test_no_review_when_two_warnings(self) -> None:
        report = DocumentEvaluationReport(
            checks=[
                DeterministicCheckResult(
                    passed=False,
                    check_name="no_keyword_loss",
                    message="Lost: Redis",
                    severity="warning",
                ),
                DeterministicCheckResult(
                    passed=False,
                    check_name="ats_keyword_preservation",
                    message="Lost: Docker",
                    severity="warning",
                ),
            ]
        )

        service = DocumentReviewService()
        requires_review, reason = service.evaluate_review_requirement(report)

        assert requires_review is False
        assert reason == "No mandatory review required"

    def test_critical_takes_precedence_over_warnings(self) -> None:
        report = DocumentEvaluationReport(
            checks=[
                DeterministicCheckResult(
                    passed=False,
                    check_name="no_hallucinated_metrics",
                    message="Critical issue",
                    severity="critical",
                ),
                DeterministicCheckResult(
                    passed=False,
                    check_name="no_keyword_loss",
                    message="Warning",
                    severity="warning",
                ),
                DeterministicCheckResult(
                    passed=False,
                    check_name="ats_keyword_preservation",
                    message="Warning",
                    severity="warning",
                ),
            ]
        )

        service = DocumentReviewService()
        requires_review, reason = service.evaluate_review_requirement(report)

        assert requires_review is True
        assert "Critical failures detected" in reason

    def test_info_severity_does_not_trigger_review(self) -> None:
        report = DocumentEvaluationReport(
            checks=[
                DeterministicCheckResult(
                    passed=False,
                    check_name="info_check",
                    message="Info message",
                    severity="info",
                ),
                DeterministicCheckResult(
                    passed=False,
                    check_name="info_check_2",
                    message="Info message 2",
                    severity="info",
                ),
                DeterministicCheckResult(
                    passed=False,
                    check_name="info_check_3",
                    message="Info message 3",
                    severity="info",
                ),
            ]
        )

        service = DocumentReviewService()
        requires_review, reason = service.evaluate_review_requirement(report)

        assert requires_review is False
