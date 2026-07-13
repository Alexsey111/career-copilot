# app\domain\career_strategy.py

"""Доменные модели карьерной стратегии (Этап 9.D).

Детерминированный, explainable план на основе уже агрегированных сигналов
(``GapTrendService`` — recurring gaps, ``SemanticRequirementMatcher`` —
релевантность gap↔target_roles). **Без AI**: learning plan не выдумывает
курсы/цены — только rule-based шаги reskilling/upskilling с объяснимым
обоснованием. ``requires_human_review`` всегда True.

См. ``docs/career_strategy.md`` (non-goals: autonomous planning, predictions,
ссылки на конкретные курсы/цены) и ``interview_prep_contract.md`` (образец
explainable roadmap).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.interview_prep import has_leadership_tokens


SEVERITY_ORDER: dict[str, int] = {"critical": 3, "important": 2, "minor": 1}

# Токены, сигнализирующие о системном дизайне / архитектуре — отдельный шаг
# ``practice_project`` (практика на проекте эффективнее «чтения»).
_SYSTEM_DESIGN_TOKENS = (
    "system design",
    "архитектур",
    "scalab",
    "highload",
    "high load",
    "distributed system",
    "распределённ",
    "распределенн",
)

# Слова-маркеры названия курса/цен — НЕ должны появляться в action/rationale
# (non-goal: ссылки на конкретные курсы/цены).
_EXTERNAL_LINK_MARKERS = ("http", "www.", "курс", "udemy", "coursera", "руб", "$", "€")


@dataclass(slots=True)
class GapSummaryItem:
    """Recurring gap, классифицированный по отношению к target_roles трека."""

    keyword: str
    count: int
    severity: str
    example_vacancy_titles: list[str] = field(default_factory=list)
    is_relevant_to_track: bool = False
    relevance_reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "keyword": self.keyword,
            "count": self.count,
            "severity": self.severity,
            "example_vacancy_titles": list(self.example_vacancy_titles),
            "is_relevant_to_track": self.is_relevant_to_track,
            "relevance_reason": self.relevance_reason,
        }


@dataclass(slots=True)
class LearningPlanStep:
    """Один шаг плана обучения (reskilling/upskilling), explainable, без ссылок."""

    order: int
    gap_keyword: str
    step_type: str
    action: str
    rationale: str
    priority: str
    estimated_effort: str
    prerequisites: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "order": self.order,
            "gap_keyword": self.gap_keyword,
            "step_type": self.step_type,
            "action": self.action,
            "rationale": self.rationale,
            "priority": self.priority,
            "estimated_effort": self.estimated_effort,
            "prerequisites": list(self.prerequisites),
        }


@dataclass(slots=True)
class LearningPlan:
    steps: list[LearningPlanStep] = field(default_factory=list)
    projected_coverage: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "steps": [s.as_dict() for s in self.steps],
            "projected_coverage": dict(self.projected_coverage),
        }


@dataclass(slots=True)
class SearchTactic:
    """Тактика поиска/нетворкинга, rule-based по типу ролей + gap severity."""

    channel_type: str
    tactic: str
    rationale: str
    priority: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "channel_type": self.channel_type,
            "tactic": self.tactic,
            "rationale": self.rationale,
            "priority": self.priority,
        }


@dataclass(slots=True)
class StrategyProvenance:
    """Provenance стратегии: источники, confidence (НЕ числовой), human review."""

    sources: list[str] = field(default_factory=list)
    confidence: str = "low"
    requires_human_review: bool = True
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "sources": list(self.sources),
            "confidence": self.confidence,
            "requires_human_review": self.requires_human_review,
            "notes": list(self.notes),
        }


@dataclass(slots=True)
class StrategyReport:
    track_id: Any
    gap_summary: list[GapSummaryItem] = field(default_factory=list)
    learning_plan: LearningPlan = field(default_factory=LearningPlan)
    search_tactics: list[SearchTactic] = field(default_factory=list)
    provenance: StrategyProvenance = field(default_factory=StrategyProvenance)

    def as_dict(self) -> dict[str, Any]:
        return {
            "track_id": str(self.track_id),
            "gap_summary": [g.as_dict() for g in self.gap_summary],
            "learning_plan": self.learning_plan.as_dict(),
            "search_tactics": [t.as_dict() for t in self.search_tactics],
            "provenance": self.provenance.as_dict(),
        }


def _has_system_design_tokens(text: str) -> bool:
    normalized = text.casefold()
    return any(token in normalized for token in _SYSTEM_DESIGN_TOKENS)


def classify_gap_relevance(
    gap_keyword: str,
    example_vacancy_titles: list[str],
    target_roles: list[str],
    matcher,
) -> tuple[bool, str | None]:
    """Классифицировать gap как relevant/other относительно target_roles трека.

    Gap relevant, если **вакансия-источник** recurring gap'а
    (``example_vacancy_titles``) соответствует одной из ``target_roles`` трека
    (через ``SemanticRequirementMatcher``). Сравнивать сам gap-keyword с role
    name бессмысленно: навык ("Kubernetes") почти не совпадает с должностью
    ("Platform Engineer"). Пустые ``target_roles`` → все gaps relevant.
    """
    roles = [r for r in (target_roles or []) if str(r or "").strip()]
    if not roles:
        return True, "no target roles specified; all gaps considered"

    for title in example_vacancy_titles or []:
        result = matcher.match(str(title or ""), roles)
        if result.matched:
            return True, (
                f"recurring in vacancy '{title}' matching target role "
                f"'{result.matched_term}'"
            )
    return False, "not in target role scope"


def _severity_priority(severity: str) -> int:
    return SEVERITY_ORDER.get(str(severity or "").strip().lower(), 0)


def build_learning_plan_steps(
    relevant_gaps: list[GapSummaryItem],
) -> list[LearningPlanStep]:
    """Детерминированные explainable шаги из relevant gaps.

    Сортировка: severity (critical→important→minor), затем count. mapping:
    critical→skill_acquisition/high/weeks; important→skill_acquisition/medium/
    weeks; minor→reading/low/days. Leadership-токены → доп. шаг
    experience_building/months; system-design-токены → practice_project/weeks.
    Никаких ссылок на курсы/цены в action/rationale.
    """
    ordered = sorted(
        relevant_gaps,
        key=lambda g: (-_severity_priority(g.severity), -g.count, g.keyword),
    )

    steps: list[LearningPlanStep] = []
    order = 0
    for gap in ordered:
        sev = (gap.severity or "").strip().lower()
        examples = ", ".join(gap.example_vacancy_titles[:2]) or "recent vacancies"
        count_phrase = f"{gap.count} vacancies" if gap.count else "recent vacancies"

        if sev == "critical":
            step_type = "skill_acquisition"
            priority = "high"
            effort = "weeks"
            action = f"Acquire hands-on proficiency in '{gap.keyword}' through deliberate practice."
            rationale = (
                f"Recurring critical gap across {count_phrase} ({examples}); "
                "closing it is blocking fit for the target role(s)."
            )
        elif sev == "important":
            step_type = "skill_acquisition"
            priority = "medium"
            effort = "weeks"
            action = f"Strengthen working knowledge of '{gap.keyword}'."
            rationale = (
                f"Recurring important gap across {count_phrase}; improving it raises fit "
                "for the target role(s)."
            )
        else:
            step_type = "reading"
            priority = "low"
            effort = "days"
            action = f"Read up on '{gap.keyword}' and note where it appears in the target roles."
            rationale = (
                f"Minor recurring gap across {count_phrase}; awareness is enough for now."
            )

        order += 1
        steps.append(
            LearningPlanStep(
                order=order,
                gap_keyword=gap.keyword,
                step_type=step_type,
                action=action,
                rationale=rationale,
                priority=priority,
                estimated_effort=effort,
            )
        )

        gap_lower = gap.keyword.casefold()
        if has_leadership_tokens(gap_lower):
            order += 1
            steps.append(
                LearningPlanStep(
                    order=order,
                    gap_keyword=gap.keyword,
                    step_type="experience_building",
                    action=(
                        f"Build a documented leadership/coordinating example covering "
                        f"'{gap.keyword}' (STAR: situation, task, action, result)."
                    ),
                    rationale=(
                        "Leadership signals are best demonstrated through a concrete "
                        "coordination story, not a course."
                    ),
                    priority="high",
                    estimated_effort="months",
                )
            )
        elif _has_system_design_tokens(gap_lower):
            order += 1
            steps.append(
                LearningPlanStep(
                    order=order,
                    gap_keyword=gap.keyword,
                    step_type="practice_project",
                    action=(
                        f"Design and document a small project exercising '{gap.keyword}' "
                        f"(trade-offs, constraints, alternatives)."
                    ),
                    rationale=(
                        "System-design gaps are closed through practice and documented "
                        "trade-offs, not reading."
                    ),
                    priority="medium",
                    estimated_effort="weeks",
                )
            )

    return steps


def build_search_tactics(
    target_roles: list[str],
    overall_severity: str | None,
) -> list[SearchTactic]:
    """Rule-based тактика поиска/нетворкинга по типу ролей + gap severity."""
    roles = [r for r in (target_roles or []) if str(r or "").strip()]
    severity = (overall_severity or "").strip().lower()
    sev_priority = {"critical": "high", "important": "medium", "minor": "low"}.get(
        severity, "medium"
    )

    if not roles:
        return [
            SearchTactic(
                channel_type="job_board",
                tactic="Monitor general job boards for roles matching your profile.",
                rationale=(
                    "configure target roles for more specific tactics"
                ),
                priority=sev_priority,
            ),
            SearchTactic(
                channel_type="referral",
                tactic="Reach out to your network for referrals to relevant openings.",
                rationale=(
                    "referrals are effective when recurring gaps make direct applications "
                    "harder; configure target roles for more specific tactics"
                ),
                priority=sev_priority,
            ),
        ]

    roles_text = ", ".join(roles[:3])
    roles_lower = " ".join(roles).casefold()
    tactics: list[SearchTactic] = []

    tactics.append(
        SearchTactic(
            channel_type="job_board",
            tactic=f"Monitor role-specific job boards for {roles_text}.",
            rationale="role-specific boards surface better-matched openings than generic feeds.",
            priority=sev_priority,
        )
    )

    if any(tok in roles_lower for tok in ("engineer", "developer", "разработчик", "инженер", "data", "backend", "frontend")):
        tactics.append(
            SearchTactic(
                channel_type="community",
                tactic=f"Participate in {roles_text} communities (forums, OSS, chats).",
                rationale=(
                    "technical roles hire heavily through community presence and "
                    "demonstrated work."
                ),
                priority="medium",
            )
        )

    if any(tok in roles_lower for tok in ("senior", "staff", "lead", "principal", "manager", "руководит")):
        tactics.append(
            SearchTactic(
                channel_type="event",
                tactic=f"Attend meetups/conferences for {roles_text} and speak where possible.",
                rationale=(
                    "senior/leadership roles are filled through visible expertise and "
                    "peer networks."
                ),
                priority="medium",
            )
        )

    if severity == "critical":
        tactics.append(
            SearchTactic(
                channel_type="referral",
                tactic="Leverage referrals before cold-applying to critical-gap roles.",
                rationale=(
                    "recurring critical gaps make cold applications harder; a referral "
                    "bypasses the keyword screen."
                ),
                priority="high",
            )
        )

    if has_leadership_tokens(roles_lower) or _has_system_design_tokens(roles_lower):
        tactics.append(
            SearchTactic(
                channel_type="content",
                tactic="Publish a short case study / write-up demonstrating the gap domain.",
                rationale=(
                    "a published case study compensates for a recurring gap by showing "
                    "applied understanding."
                ),
                priority="medium",
            )
        )

    return tactics


def build_projected_coverage(
    steps: list[LearningPlanStep],
    all_recurring_gaps: list[GapSummaryItem],
) -> dict[str, Any]:
    """Качественная оценка покрытия шагами (без числовых прогнозов).

    Сравнивает адресованные шагами gap-ключевые слова (relevant subset) со
    ВСЕМИ recurring gaps (relevant + other) — показывая, что план покрывает
    только часть, релевантную треку. Если все gaps relevant — coverage ``full``.
    """
    addressed = sorted({s.gap_keyword for s in steps})
    critical_gaps = [g for g in all_recurring_gaps if (g.severity or "").lower() == "critical"]
    important_gaps = [g for g in all_recurring_gaps if (g.severity or "").lower() == "important"]

    addressed_set = set(addressed)
    critical_covered = [g for g in critical_gaps if g.keyword in addressed_set]
    important_covered = [g for g in important_gaps if g.keyword in addressed_set]

    if not critical_gaps and not important_gaps:
        label = "partial"
    elif critical_gaps and len(critical_covered) == len(critical_gaps):
        label = "full"
    elif critical_covered and (not important_gaps or len(important_covered) == len(important_gaps)):
        label = "substantial"
    else:
        label = "partial"

    return {
        "addressed_gap_keywords": addressed,
        "estimated_coverage_after": label,
    }


def assert_no_external_course_references(steps: list[LearningPlanStep]) -> bool:
    """Guard: в action/rationale нет ссылок на курсы/цены (non-goal). Для тестов."""
    for step in steps:
        text = f"{step.action} {step.rationale}".casefold()
        if any(marker in text for marker in _EXTERNAL_LINK_MARKERS):
            return False
    return True