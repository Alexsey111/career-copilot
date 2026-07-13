from __future__ import annotations

from app.domain.case_prep import (
    STABLE_CASE_TYPES,
    PracticeCase,
    assert_no_fabricated_specifics,
    build_case,
    build_meta,
    build_rubric,
    build_suggested_approach,
    select_case_types,
)


def _req(text: str, *, scope: str = "must_have", severity: str = "important") -> dict:
    return {"requirement": text, "scope": scope, "severity": severity, "supporting_evidence": []}


def _gap(text: str, severity: str = "critical") -> dict:
    return {"requirement": text, "keyword": text, "severity": severity}


# --- select_case_types -------------------------------------------------------


def test_select_case_types_leadership_and_seniority_yields_system_design_and_behavioral() -> None:
    requirements = [_req("Lead a senior backend team"), _req("Ownership of the service")]
    types = select_case_types(requirements, [])
    # seniority-маркер "senior" + leadership → system_design; leadership → behavioral_case.
    assert "system_design" in types
    assert "behavioral_case" in types
    # Порядок приоритета: system_design раньше behavioral_case.
    assert types.index("system_design") < types.index("behavioral_case")


def test_select_case_types_debug_tokens_yield_debugging_scenario() -> None:
    requirements = [_req("On-call incident debugging and root cause analysis")]
    types = select_case_types(requirements, [])
    assert "debugging_scenario" in types


def test_select_case_types_data_tokens_yield_data_analysis() -> None:
    requirements = [_req("SQL, ETL pipelines and dashboards for analytics")]
    types = select_case_types(requirements, [])
    assert "data_analysis" in types


def test_select_case_types_critical_gap_yields_take_home_brief() -> None:
    requirements = [_req("Some skill", severity="critical")]
    types = select_case_types(requirements, [])
    assert "take_home_brief" in types


def test_select_case_types_critical_gap_in_gaps_yields_take_home_brief() -> None:
    types = select_case_types([], [_gap("Kubernetes", "critical")])
    assert "take_home_brief" in types


def test_select_case_types_empty_falls_back_to_behavioral_case() -> None:
    assert select_case_types([], []) == ["behavioral_case"]


def test_select_case_types_dedup_and_priority_order() -> None:
    # System-design-токены + leadership + seniority + critical → все пять типов,
    # в стабильном порядке приоритета, без дубликатов.
    requirements = [
        _req("Senior system design and leadership at scale", severity="critical"),
    ]
    types = select_case_types(requirements, [])
    assert types == list(dict.fromkeys(types))  # нет дублей
    # Порядок приоритета.
    priority = ("system_design", "debugging_scenario", "data_analysis", "behavioral_case", "take_home_brief")
    indexes = [priority.index(t) for t in types]
    assert indexes == sorted(indexes)


def test_select_case_types_respects_max_cases() -> None:
    requirements = [
        _req("Senior system design leadership with SQL analytics and incident debugging", severity="critical"),
    ]
    types = select_case_types(requirements, [], max_cases=2)
    assert len(types) == 2


# --- build_rubric / build_suggested_approach ---------------------------------


def test_build_rubric_has_at_least_four_criteria_for_each_type() -> None:
    for case_type in STABLE_CASE_TYPES:
        rubric = build_rubric(case_type)
        assert len(rubric) >= 4, case_type
        assert all(isinstance(item, str) and item for item in rubric)


def test_build_suggested_approach_has_steps_for_each_type() -> None:
    for case_type in STABLE_CASE_TYPES:
        steps = build_suggested_approach(case_type)
        assert len(steps) >= 3, case_type
        assert all(isinstance(item, str) and item for item in steps)


# --- build_case --------------------------------------------------------------


def test_build_case_has_no_fabricated_specifics() -> None:
    cases = [
        build_case("system_design", requirement=_req("Design a distributed cache")),
        build_case("debugging_scenario", requirement=_req("Investigate an incident in the payment service")),
        build_case("data_analysis", requirement=_req("Conversion funnel analytics")),
        build_case("behavioral_case", requirement=_req("Mentoring and leadership")),
        build_case("take_home_brief", gap=_gap("Kubernetes", "critical")),
    ]
    assert assert_no_fabricated_specifics(cases) is True


def test_build_case_guard_catches_fabricated_company() -> None:
    # Если в title/prompt случайно попадёт acme/inc — guard срабатывает.
    case = PracticeCase(
        case_id="x",
        case_type="system_design",
        title="System design practice — Acme",
        prompt="Design for Acme",
        framework="hypothesis-driven",
        time_guidance="60-90 minutes",
    )
    assert assert_no_fabricated_specifics([case]) is False


def test_build_case_prompt_contains_requirement_keyword() -> None:
    case = build_case("system_design", requirement=_req("Design a distributed cache"))
    assert "distributed cache" in case.prompt


def test_build_case_uses_gap_keyword_when_requirement_absent() -> None:
    case = build_case("take_home_brief", gap=_gap("Kubernetes", "critical"))
    assert "Kubernetes" in case.prompt
    assert case.gap_severity == "critical"


def test_build_case_id_is_deterministic() -> None:
    req = _req("Design a distributed cache")
    c1 = build_case("system_design", requirement=req)
    c2 = build_case("system_design", requirement=req)
    assert c1.case_id == c2.case_id
    assert c1.case_id.startswith("ipc_")


def test_build_case_id_differs_for_different_requirements() -> None:
    c1 = build_case("system_design", requirement=_req("Design a distributed cache"))
    c2 = build_case("system_design", requirement=_req("Design a rate limiter"))
    assert c1.case_id != c2.case_id


def test_build_case_provenance_requires_human_review() -> None:
    case = build_case("behavioral_case", requirement=_req("Mentoring"))
    assert case.provenance.requires_human_review is True
    assert "vacancy_fit" in case.provenance.sources


def test_build_case_framework_mapping() -> None:
    assert build_case("system_design", requirement=_req("x")).framework == "hypothesis-driven"
    assert build_case("debugging_scenario", requirement=_req("x")).framework == "hypothesis-driven"
    assert build_case("data_analysis", requirement=_req("x")).framework == "structured_walkthrough"
    assert build_case("behavioral_case", requirement=_req("x")).framework == "STAR"
    assert build_case("take_home_brief", gap=_gap("x")).framework == "RTL"


def test_build_case_time_guidance_is_band_without_dates() -> None:
    import re

    for case_type in STABLE_CASE_TYPES:
        case = build_case(case_type, requirement=_req("sample requirement"))
        # Band-формат, без конкретных дат/чисел-дедлайнов.
        assert case.time_guidance
        assert not re.search(r"\b20\d{2}\b", case.time_guidance)


# --- build_meta --------------------------------------------------------------


def test_build_meta_counts_match_case_types() -> None:
    case_types = ["system_design", "system_design", "behavioral_case"]
    meta = build_meta(case_types, [])
    assert meta["total"] == 3
    assert meta["case_type_counts"]["system_design"] == 2
    assert meta["case_type_counts"]["behavioral_case"] == 1


def test_build_meta_has_critical_gap_flag() -> None:
    requirements = [_req("Kubernetes", severity="critical")]
    meta = build_meta([], requirements)
    assert meta["has_critical_gap"] is True


def test_build_meta_no_critical_gap_flag() -> None:
    requirements = [_req("Python", severity="important")]
    meta = build_meta([], requirements)
    assert meta["has_critical_gap"] is False