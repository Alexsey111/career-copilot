# tests/evals/test_application_status_transitions.py

from __future__ import annotations

import pytest

from app.domain.application_models import (
    is_valid_transition,
    get_allowed_transitions,
)


class TestApplicationStatusTransitions:
    """Тесты для статусных переходов application."""

    def test_valid_transitions(self) -> None:
        # draft → ready
        assert is_valid_transition("draft", "ready") is True
        # ready → applied
        assert is_valid_transition("ready", "applied") is True
        # applied → screening
        assert is_valid_transition("applied", "screening") is True
        # screening → interview
        assert is_valid_transition("screening", "interview") is True
        # interview → offer
        assert is_valid_transition("interview", "offer") is True

    def test_self_transitions(self) -> None:
        # Можно оставаться в том же статусе
        assert is_valid_transition("draft", "draft") is True
        # Final states не имеют self-transitions
        assert is_valid_transition("rejected", "rejected") is False
        assert is_valid_transition("offer", "offer") is False

    def test_rejected_transitions(self) -> None:
        # Нельзя перейти из rejected
        assert is_valid_transition("rejected", "draft") is False
        assert is_valid_transition("rejected", "interview") is False

    def test_offer_is_final(self) -> None:
        # offer - финальное состояние
        assert is_valid_transition("offer", "draft") is False
        assert is_valid_transition("offer", "rejected") is False

    def test_withdrawn_is_final(self) -> None:
        # withdrawn - финальное состояние
        assert is_valid_transition("withdrawn", "applied") is False
        assert is_valid_transition("withdrawn", "screening") is False

    def test_get_allowed_transitions(self) -> None:
        assert get_allowed_transitions("draft") == {"ready", "draft"}
        assert get_allowed_transitions("ready") == {"applied", "draft"}
        assert get_allowed_transitions("applied") == {"screening", "interview", "rejected", "withdrawn"}
        assert get_allowed_transitions("offer") == set()
        assert get_allowed_transitions("rejected") == set()

    def test_invalid_transition_direct(self) -> None:
        # draft → interview (пропуск шагов)
        assert is_valid_transition("draft", "interview") is False
        # applied → offer (пропуск шагов)
        assert is_valid_transition("applied", "offer") is False
