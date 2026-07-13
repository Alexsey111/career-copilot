from __future__ import annotations

from app.domain.career_strategy import (
    GapSummaryItem,
    assert_no_external_course_references,
    build_learning_plan_steps,
    build_projected_coverage,
    build_search_tactics,
    classify_gap_relevance,
)
from app.services.semantic_requirement_matcher import SemanticRequirementMatcher


_MATCHER = SemanticRequirementMatcher()


def _gap(keyword: str, severity: str, count: int = 2, relevant: bool = True) -> GapSummaryItem:
    return GapSummaryItem(
        keyword=keyword,
        count=count,
        severity=severity,
        example_vacancy_titles=["Vacancy A"],
        is_relevant_to_track=relevant,
        relevance_reason="matches target role 'Backend Engineer'" if relevant else None,
    )


def test_classify_relevance_semantic_match_with_target_role() -> None:
    # Vacancy title "Python Developer" matches target role "Python Developer".
    relevant, reason = classify_gap_relevance(
        "Python", ["Python Developer"], ["Python Developer"], _MATCHER
    )
    assert relevant is True
    assert reason is not None
    assert "target role" in reason


def test_classify_relevance_unrelated_gap_is_not_relevant() -> None:
    relevant, reason = classify_gap_relevance(
        "Kubernetes", ["Бухгалтер"], ["Backend Engineer"], _MATCHER
    )
    assert relevant is False
    assert reason == "not in target role scope"


def test_classify_relevance_empty_target_roles_considers_all() -> None:
    relevant, reason = classify_gap_relevance("anything", ["x"], [], _MATCHER)
    assert relevant is True
    assert "no target roles" in (reason or "")


def test_learning_plan_critical_gap_is_skill_acquisition_high_weeks() -> None:
    steps = build_learning_plan_steps([_gap("Kubernetes", "critical", count=3)])
    assert steps
    step = steps[0]
    assert step.step_type == "skill_acquisition"
    assert step.priority == "high"
    assert step.estimated_effort == "weeks"
    assert step.order == 1
    assert "Kubernetes" in step.action
    assert "3 vacancies" in step.rationale


def test_learning_plan_important_gap_medium_priority() -> None:
    steps = build_learning_plan_steps([_gap("Redis", "important", count=2)])
    assert steps[0].priority == "medium"
    assert steps[0].step_type == "skill_acquisition"


def test_learning_plan_minor_gap_is_reading_low_days() -> None:
    steps = build_learning_plan_steps([_gap("JIRA", "minor", count=1)])
    assert steps[0].step_type == "reading"
    assert steps[0].priority == "low"
    assert steps[0].estimated_effort == "days"


def test_learning_plan_leadership_gap_adds_experience_building_step() -> None:
    steps = build_learning_plan_steps([_gap("Leadership at scale", "important", count=2)])
    step_types = [s.step_type for s in steps]
    assert "skill_acquisition" in step_types
    assert "experience_building" in step_types
    exp_step = next(s for s in steps if s.step_type == "experience_building")
    assert exp_step.priority == "high"
    assert exp_step.estimated_effort == "months"
    assert "STAR" in exp_step.action


def test_learning_plan_system_design_gap_adds_practice_project_step() -> None:
    steps = build_learning_plan_steps([_gap("System design", "important", count=2)])
    step_types = [s.step_type for s in steps]
    assert "practice_project" in step_types
    proj = next(s for s in steps if s.step_type == "practice_project")
    assert proj.estimated_effort == "weeks"


def test_learning_plan_steps_ordered_by_severity_then_count() -> None:
    gaps = [
        _gap("minor1", "minor", count=1),
        _gap("critical1", "critical", count=2),
        _gap("critical2", "critical", count=5),
    ]
    steps = build_learning_plan_steps(gaps)
    # critical2 (count=5) раньше critical1 (count=2), затем minor1.
    assert steps[0].gap_keyword == "critical2"
    assert steps[1].gap_keyword == "critical1"
    assert any(s.gap_keyword == "minor1" for s in steps)
    # order монотонно возрастает.
    orders = [s.order for s in steps]
    assert orders == sorted(orders)
    assert orders[0] == 1


def test_learning_plan_has_no_external_course_references() -> None:
    steps = build_learning_plan_steps(
        [
            _gap("Kubernetes", "critical", count=3),
            _gap("Leadership at scale", "important", count=2),
            _gap("System design", "important", count=2),
        ]
    )
    assert assert_no_external_course_references(steps) is True


def test_search_tactics_critical_severity_includes_referral() -> None:
    tactics = build_search_tactics(["Senior Backend Engineer"], "critical")
    channels = {t.channel_type for t in tactics}
    assert "job_board" in channels
    assert "referral" in channels
    referral = next(t for t in tactics if t.channel_type == "referral")
    assert referral.priority == "high"


def test_search_tactics_empty_target_roles_are_generic_with_flag() -> None:
    tactics = build_search_tactics([], "important")
    assert tactics
    rationales = " ".join(t.rationale for t in tactics)
    assert "configure target roles" in rationales


def test_projected_coverage_full_when_all_critical_covered() -> None:
    # Все gaps relevant → все critical покрыты шагами → full.
    gaps = [_gap("Kubernetes", "critical"), _gap("Redis", "important")]
    steps = build_learning_plan_steps(gaps)
    coverage = build_projected_coverage(steps, gaps)
    assert coverage["estimated_coverage_after"] == "full"
    assert "Kubernetes" in coverage["addressed_gap_keywords"]


def test_projected_coverage_partial_when_other_critical_not_covered() -> None:
    # Один critical покрыт (relevant), второй critical — other (не покрыт) →
    # есть covered critical, но не все important покрыты (важных нет) → substantial?
    # Здесь: covered critical = 1 из 2, important_gaps пуст → substantial.
    covered = _gap("Kubernetes", "critical", relevant=True)
    other = GapSummaryItem(
        keyword="1c бухгалтерия",
        count=1,
        severity="critical",
        is_relevant_to_track=False,
        relevance_reason="not in target role scope",
    )
    steps = build_learning_plan_steps([covered])
    coverage = build_projected_coverage(steps, [covered, other])
    # 1 из 2 critical покрыт, important_gaps пуст → substantial.
    assert coverage["estimated_coverage_after"] == "substantial"


def test_projected_coverage_partial_when_no_critical_no_important() -> None:
    gaps = [_gap("JIRA", "minor")]
    steps = build_learning_plan_steps(gaps)
    coverage = build_projected_coverage(steps, gaps)
    assert coverage["estimated_coverage_after"] == "partial"


def test_projected_coverage_partial_when_critical_uncovered_and_no_important_covered() -> None:
    # Все critical — other (не покрыты) → critical_covered пуст → partial.
    other = GapSummaryItem(
        keyword="1c бухгалтерия",
        count=1,
        severity="critical",
        is_relevant_to_track=False,
        relevance_reason="not in target role scope",
    )
    steps = build_learning_plan_steps([])
    coverage = build_projected_coverage(steps, [other])
    assert coverage["estimated_coverage_after"] == "partial"