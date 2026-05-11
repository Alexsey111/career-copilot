from app.domain.retrieval_models import RetrievalDecision, RetrievalTrace


class TestRetrievalDecision:
    """Тесты для RetrievalDecision модели."""

    def test_retrieval_decision_with_results(self) -> None:
        """Решение с найденными достижениями."""
        decision = RetrievalDecision(
            requirement_id="req-1",
            requirement_text="Python development",
            retrieved_achievement_ids=["ach-1", "ach-2"],
            retrieval_scores={"ach-1": 0.85, "ach-2": 0.7},
            retrieval_method="hybrid",
            threshold_used=0.3,
        )

        assert decision.is_empty is False
        assert decision.top_achievement_id == "ach-1"

    def test_retrieval_decision_empty(self) -> None:
        """Решение без результатов."""
        decision = RetrievalDecision(
            requirement_id="req-2",
            requirement_text="Management skills",
            retrieved_achievement_ids=[],
            retrieval_scores={},
            retrieval_method="keyword_match",
            threshold_used=0.3,
        )

        assert decision.is_empty is True
        assert decision.top_achievement_id is None


class TestRetrievalTrace:
    """Тесты для RetrievalTrace модели."""

    def test_retrieval_trace_coverage_rate(self) -> None:
        """Процент покрытых требований."""
        trace = RetrievalTrace(
            decisions=[
                RetrievalDecision(
                    requirement_id="req-1",
                    requirement_text="req1",
                    retrieved_achievement_ids=["ach-1"],
                    retrieval_scores={"ach-1": 0.8},
                    retrieval_method="semantic",
                    threshold_used=0.3,
                ),
                RetrievalDecision(
                    requirement_id="req-2",
                    requirement_text="req2",
                    retrieved_achievement_ids=[],
                    retrieval_scores={},
                    retrieval_method="semantic",
                    threshold_used=0.3,
                ),
                RetrievalDecision(
                    requirement_id="req-3",
                    requirement_text="req3",
                    retrieved_achievement_ids=["ach-2"],
                    retrieval_scores={"ach-2": 0.6},
                    retrieval_method="semantic",
                    threshold_used=0.3,
                ),
            ],
            total_achievements_available=10,
        )

        assert abs(trace.coverage_rate - 2 / 3) < 0.01
        assert trace.total_achievements_retrieved == 0  # не вычисляется автоматически

    def test_retrieval_trace_empty(self) -> None:
        """Пустая трассировка."""
        trace = RetrievalTrace()

        assert trace.coverage_rate == 0.0
        assert len(trace.decisions) == 0
