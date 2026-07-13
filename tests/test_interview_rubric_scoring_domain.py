from __future__ import annotations

from app.domain.case_prep import STABLE_CASE_TYPES, build_rubric
from app.domain.interview_rubric_scoring import (
    _grade_for,
    _score_to_level,
    _RUBRIC_TOKENS,
    assert_scoring_deterministic,
    build_cross_session_progress,
    score_answer_against_rubric,
)


def _attempt(case_type: str, *, overall: float, scores: dict[str, int]) -> dict:
    """Снапшот попытки для build_cross_session_progress (как отдаёт репозиторий)."""
    return {
        "overall_score": overall,
        "criterion_scores_json": [
            {"criterion": c, "score": s, "level": _score_to_level(s), "reason": ""}
            for c, s in scores.items()
        ],
    }


def test_system_design_all_markers_yields_high_overall_excellent() -> None:
    tokens = []
    for crit_tokens in _RUBRIC_TOKENS["system_design"].values():
        tokens.extend(crit_tokens)
    answer = " ".join(tokens)
    report = score_answer_against_rubric("system_design", answer)
    assert all(c.level == "high" for c in report.criterion_scores)
    assert report.overall_score == 100.0
    assert report.grade == "excellent"
    assert report.requires_human_review is True


def test_empty_answer_all_none_weak_with_coaching() -> None:
    report = score_answer_against_rubric("system_design", "   ")
    assert all(c.level == "none" for c in report.criterion_scores)
    assert all(c.score == 0 for c in report.criterion_scores)
    assert report.overall_score == 0.0
    assert report.grade == "weak"
    assert any("empty" in note for note in report.feedback["issues"])
    assert any("below 50" in note for note in report.feedback["issues"])


def test_partial_answer_mixed_levels_needs_work() -> None:
    answer = "scalab throughput latency failure outage retry tradeoff compromise alternatively"
    report = score_answer_against_rubric("system_design", answer)
    levels = {c.level for c in report.criterion_scores}
    assert "high" in levels
    assert "none" in levels
    assert report.grade == "needs_work"


def test_score_to_level_clamps() -> None:
    assert _score_to_level(0) == "none"
    assert _score_to_level(1) == "low"
    assert _score_to_level(2) == "medium"
    assert _score_to_level(3) == "high"
    assert _score_to_level(5) == "high"
    assert _score_to_level(-1) == "none"


def test_grade_for_thresholds() -> None:
    assert _grade_for(85.0) == "excellent"
    assert _grade_for(70.0) == "good"
    assert _grade_for(50.0) == "needs_work"
    assert _grade_for(49.9) == "weak"


def test_overall_normalisation_three_of_five_high_is_60() -> None:
    # 3 критерия score=3, 2 — score=0 → sum=9, overall=round(9/5*100/3,1)=60.0
    answer = "scalab throughput latency failure outage retry tradeoff compromise alternatively"
    report = score_answer_against_rubric("system_design", answer)
    high = sum(1 for c in report.criterion_scores if c.score == 3)
    zero = sum(1 for c in report.criterion_scores if c.score == 0)
    assert high == 3
    assert zero == 2
    assert report.overall_score == 60.0


def test_feedback_strengths_are_high_criteria() -> None:
    tokens = []
    for crit_tokens in _RUBRIC_TOKENS["behavioral_case"].values():
        tokens.extend(crit_tokens)
    report = score_answer_against_rubric("behavioral_case", " ".join(tokens))
    high_criteria = {c.criterion for c in report.criterion_scores if c.level == "high"}
    assert set(report.feedback["strengths"]) == high_criteria


def test_feedback_improvements_for_none_and_low() -> None:
    report = score_answer_against_rubric("system_design", "scalab throughput latency")
    improvements = report.feedback["improvements"]
    weak_criteria = {
        c.criterion for c in report.criterion_scores if c.level in ("none", "low")
    }
    assert set(improvements) == {f"Address: {c}" for c in weak_criteria}
    assert all(imp.startswith("Address: ") for imp in improvements)


def test_issues_coaching_note_when_overall_below_50() -> None:
    report = score_answer_against_rubric("system_design", "scalab")
    assert report.overall_score < 50.0
    assert any("below 50" in note for note in report.feedback["issues"])


def test_requires_human_review_always_true() -> None:
    tokens = []
    for crit_tokens in _RUBRIC_TOKENS["system_design"].values():
        tokens.extend(crit_tokens)
    high = score_answer_against_rubric("system_design", " ".join(tokens))
    empty = score_answer_against_rubric("system_design", "")
    assert high.requires_human_review is True
    assert empty.requires_human_review is True


def test_every_case_type_synthetic_answer_all_high_overall_100() -> None:
    # Гарантирует, что все 25 критериев имеют непустые token-наборы.
    for case_type in STABLE_CASE_TYPES:
        tokens = []
        for crit_tokens in _RUBRIC_TOKENS[case_type].values():
            assert len(crit_tokens) > 0, f"empty tokens for {case_type}"
            tokens.extend(crit_tokens)
        report = score_answer_against_rubric(case_type, " ".join(tokens))
        assert all(c.level == "high" for c in report.criterion_scores), case_type
        assert report.overall_score == 100.0, case_type
        assert len(report.criterion_scores) == len(build_rubric(case_type))


def test_assert_scoring_deterministic() -> None:
    answer = "scalab throughput latency failure outage retry"
    assert assert_scoring_deterministic("system_design", answer, runs=3) is True
    assert assert_scoring_deterministic("bogus_case", answer) is False


def test_reason_does_not_leak_answer_substrings() -> None:
    answer = "ivan@example.com scalable throughput latency failure outage retry tradeoff"
    report = score_answer_against_rubric("system_design", answer)
    blob = " ".join(c.reason for c in report.criterion_scores)
    blob += " " + " ".join(
        s for v in report.feedback.values() for s in v
    )
    assert "ivan@example.com" not in blob
    # reason ссылается на имена токенов, не на подстроки ответа-ПДн.
    assert all("ivan" not in c.reason for c in report.criterion_scores)


def test_cross_session_progress_empty() -> None:
    progress = build_cross_session_progress([])
    assert progress["total_attempts"] == 0
    assert progress["reason"] == "no attempts yet"
    assert progress["overall"] is None
    assert progress["per_criterion"] == []


def test_cross_session_progress_improving() -> None:
    crits = build_rubric("system_design")
    attempts = [
        _attempt("system_design", overall=30.0, scores={crits[0]: 0, crits[1]: 1, crits[2]: 0, crits[3]: 0, crits[4]: 0}),
        _attempt("system_design", overall=60.0, scores={crits[0]: 2, crits[1]: 2, crits[2]: 1, crits[3]: 1, crits[4]: 0}),
        _attempt("system_design", overall=85.0, scores={crits[0]: 3, crits[1]: 3, crits[2]: 3, crits[3]: 2, crits[4]: 1}),
    ]
    progress = build_cross_session_progress(attempts)
    assert progress["total_attempts"] == 3
    assert progress["overall"]["first"] == 30.0
    assert progress["overall"]["last"] == 85.0
    assert progress["overall"]["best"] == 85.0
    assert progress["overall"]["improvement"] == 55.0
    assert progress["overall"]["trend"] == "improving"


def test_cross_session_progress_declining() -> None:
    crits = build_rubric("system_design")
    attempts = [
        _attempt("system_design", overall=80.0, scores={crits[0]: 3, crits[1]: 3, crits[2]: 2, crits[3]: 2, crits[4]: 1}),
        _attempt("system_design", overall=60.0, scores={crits[0]: 2, crits[1]: 2, crits[2]: 1, crits[3]: 1, crits[4]: 0}),
        _attempt("system_design", overall=40.0, scores={crits[0]: 1, crits[1]: 1, crits[2]: 0, crits[3]: 0, crits[4]: 0}),
    ]
    progress = build_cross_session_progress(attempts)
    assert progress["overall"]["trend"] == "declining"
    assert progress["overall"]["improvement"] == -40.0


def test_cross_session_progress_stable() -> None:
    crits = build_rubric("system_design")
    attempts = [
        _attempt("system_design", overall=60.0, scores={crits[0]: 2, crits[1]: 2, crits[2]: 1, crits[3]: 1, crits[4]: 1}),
        _attempt("system_design", overall=60.5, scores={crits[0]: 2, crits[1]: 2, crits[2]: 1, crits[3]: 1, crits[4]: 1}),
        _attempt("system_design", overall=60.2, scores={crits[0]: 2, crits[1]: 2, crits[2]: 1, crits[3]: 1, crits[4]: 1}),
    ]
    progress = build_cross_session_progress(attempts)
    assert progress["overall"]["trend"] == "stable"


def test_cross_session_progress_per_criterion_aggregate() -> None:
    crits = build_rubric("system_design")
    attempts = [
        _attempt("system_design", overall=20.0, scores={crits[0]: 0, crits[1]: 1, crits[2]: 0, crits[3]: 0, crits[4]: 0}),
        _attempt("system_design", overall=70.0, scores={crits[0]: 3, crits[1]: 1, crits[2]: 3, crits[3]: 0, crits[4]: 2}),
    ]
    progress = build_cross_session_progress(attempts)
    by_crit = {p["criterion"]: p for p in progress["per_criterion"]}
    assert by_crit[crits[0]] == {"criterion": crits[0], "first": 0, "last": 3, "best": 3, "improvement": 3}
    assert by_crit[crits[1]] == {"criterion": crits[1], "first": 1, "last": 1, "best": 1, "improvement": 0}
    assert by_crit[crits[3]] == {"criterion": crits[3], "first": 0, "last": 0, "best": 0, "improvement": 0}


def test_cross_session_progress_has_no_forecast_terms() -> None:
    crits = build_rubric("system_design")
    attempts = [_attempt("system_design", overall=50.0, scores={c: 1 for c in crits})]
    progress = build_cross_session_progress(attempts)
    blob = repr(progress)
    for term in ("forecast", "predicted", "probability"):
        assert term not in blob.lower()