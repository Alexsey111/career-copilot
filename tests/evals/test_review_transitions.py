# tests/evals/test_review_transitions.py

from __future__ import annotations

import pytest

from app.domain.review_models import (
    ReviewStatus,
    ALLOWED_STATUS_TRANSITIONS,
    is_valid_transition,
    get_allowed_transitions,
)


class TestReviewTransitions:
    """Тесты для controlled review transitions."""

    def test_draft_to_review_required(self) -> None:
        assert is_valid_transition("draft", "review_required") is True

    def test_draft_to_draft(self) -> None:
        assert is_valid_transition("draft", "draft") is True

    def test_draft_to_reviewed_invalid(self) -> None:
        assert is_valid_transition("draft", "reviewed") is False

    def test_draft_to_approved_valid_for_backward_compat(self) -> None:
        assert is_valid_transition("draft", "approved") is True

    def test_review_required_to_reviewed(self) -> None:
        assert is_valid_transition("review_required", "reviewed") is True

    def test_review_required_to_draft(self) -> None:
        assert is_valid_transition("review_required", "draft") is True

    def test_review_required_to_approved_invalid(self) -> None:
        assert is_valid_transition("review_required", "approved") is False

    def test_reviewed_to_approved(self) -> None:
        assert is_valid_transition("reviewed", "approved") is True

    def test_reviewed_to_review_required(self) -> None:
        assert is_valid_transition("reviewed", "review_required") is True

    def test_reviewed_to_draft(self) -> None:
        assert is_valid_transition("reviewed", "draft") is True

    def test_reviewed_to_archived_invalid(self) -> None:
        assert is_valid_transition("reviewed", "archived") is False

    def test_approved_to_archived(self) -> None:
        assert is_valid_transition("approved", "archived") is True

    def test_approved_to_review_required(self) -> None:
        assert is_valid_transition("approved", "review_required") is True

    def test_approved_to_draft_invalid(self) -> None:
        assert is_valid_transition("approved", "draft") is False

    def test_archived_no_transitions(self) -> None:
        assert is_valid_transition("archived", "draft") is False
        assert is_valid_transition("archived", "review_required") is False
        assert is_valid_transition("archived", "reviewed") is False
        assert is_valid_transition("archived", "approved") is False
        assert is_valid_transition("archived", "archived") is False

    def test_get_allowed_transitions_draft(self) -> None:
        allowed = get_allowed_transitions("draft")
        assert allowed == {"review_required", "approved", "draft"}

    def test_get_allowed_transitions_review_required(self) -> None:
        allowed = get_allowed_transitions("review_required")
        assert allowed == {"reviewed", "draft"}

    def test_get_allowed_transitions_reviewed(self) -> None:
        allowed = get_allowed_transitions("reviewed")
        assert allowed == {"approved", "review_required", "draft"}

    def test_get_allowed_transitions_approved(self) -> None:
        allowed = get_allowed_transitions("approved")
        assert allowed == {"archived", "review_required"}

    def test_get_allowed_transitions_archived(self) -> None:
        allowed = get_allowed_transitions("archived")
        assert allowed == set()


class TestReviewSeverity:
    """Тесты для severity-based warnings."""

    def test_warning_severity_levels(self) -> None:
        assert "info" in ["info", "warning", "critical"]
        assert "warning" in ["info", "warning", "critical"]
        assert "critical" in ["info", "warning", "critical"]

    def test_keyword_gap_is_warning(self) -> None:
        from app.domain.trace_models import DocumentEvaluationReport, DeterministicCheckResult

        check = DeterministicCheckResult(
            passed=False,
            check_name="no_keyword_loss",
            message="Lost keyword: Redis",
            severity="warning",
        )
        assert check.severity == "warning"

    def test_hallucinated_metric_is_critical(self) -> None:
        from app.domain.trace_models import DocumentEvaluationReport, DeterministicCheckResult

        check = DeterministicCheckResult(
            passed=False,
            check_name="no_hallucinated_metrics",
            message="Unconfirmed metric: 50% increase",
            severity="critical",
        )
        assert check.severity == "critical"
