# app\domain\interview_rubric_scoring.py

"""Per-criterion rubric scoring ответов на practice-кейсы (Этап 9.F).

Детерминированный keyword-heuristic scoring **без AI**: для каждого стабильного
критерия кейса (``build_rubric(case_type)`` — 5 критериев × 5 case_type) ищем
маркерные термины в ответе кандидата, score = ``min(3, count уникальных токенов)``
→ ``none``/``low``/``medium``/``high``. ``overall`` 0-100, ``grade``.

Scoring — **coaching artifact, не factual claim**: ``requires_human_review``
всегда True; ``high`` = нужная лексика присутствует, **не** «ответ верный».
``reason`` ссылается на имена токенов, **не** на подстроки ответа (ПДн не утекает
в JSON). ``build_cross_session_progress`` — backward-looking snapshot
(first/last/best/improvement + coarse trend), **без** числовых прогнозов.

См. ``docs/interview_prep_contract.md`` (Answer Rubric Scoring, Cross-Session
Progress). Переиспользует ``STABLE_CASE_TYPES`` и ``build_rubric`` из
``app/domain/case_prep.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.case_prep import STABLE_CASE_TYPES, build_rubric


RUBRIC_VERSION = "deterministic_v1"

_LEVEL_BY_SCORE: dict[int, str] = {0: "none", 1: "low", 2: "medium", 3: "high"}

# Пороги grade: ((min_overall, grade), ...) — первое совпадение сверху.
_GRADE_THRESHOLDS: tuple[tuple[float, str], ...] = (
    (85.0, "excellent"),
    (70.0, "good"),
    (50.0, "needs_work"),
    (0.0, "weak"),
)


# Маркерные термины для каждого критерия каждого case_type. Ключ-критерий —
# точная строка из ``build_rubric(case_type)``. Проверяются casefold-подстрокой
# (как ``_has_token`` в case_prep). Полное покрытие 25 критериев (no empty tuple).
_RUBRIC_TOKENS: dict[str, dict[str, tuple[str, ...]]] = {
    "system_design": {
        "Scalability is considered and quantified where possible": (
            "scalab", "throughput", "latency", "load", "rps", "qps",
            "capacity", "bottleneck", "shard", "partition", "replica",
            "cache", "horizontal", "вертикал", "масштаб", "нагрузк",
            "пропускн", "ёмкость", "емкость",
        ),
        "Failure modes and graceful degradation are identified": (
            "failure", "degrade", "degradation", "outage", "retry",
            "fallback", "circuit", "bulkhead", "timeout", "backpressure",
            "graceful", "отказ", "деградац", "падение", "резерв",
        ),
        "Trade-offs are explicit, with alternatives considered": (
            "tradeoff", "trade-off", "alternatively", "versus", "vs.",
            "on the other hand", "instead of", "compromise", "chosen because",
            "компромисс", "вместо", "альтернатив", "с другой стороны",
        ),
        "Data flow and component responsibilities are clear": (
            "component", "service", "queue", "database", "cache",
            "data flow", "dataflow", "flow", "api", "gateway",
            "load balancer", "cdn", "broker", "kafka",
            "компонент", "сервис", "очередь", "база", "поток",
        ),
        "Assumptions are stated and bounded": (
            "assume", "assumption", "given that", "suppose",
            "for the sake of", "boundary",
            "предполож", "допущен", "исходя из",
        ),
    },
    "debugging_scenario": {
        "A hypothesis is formed before acting": (
            "hypothesis", "i suspect", "suspect", "could be",
            "likely cause", "guess", "theory",
            "гипотез", "предполагаю", "подозреваю",
        ),
        "Evidence and logs are used to confirm or refute it": (
            "log", "logs", "logging", "metric", "dashboard", "trace",
            "span", "evidence", "observe", "alert", "monitoring",
            "лог", "метрик", "дашборд", "наблюд", "трейс",
        ),
        "Variables are isolated one at a time": (
            "isolate", "one variable", "one at a time", "control",
            "bisection", "bisect", "binary search", "controlled change",
            "single change", "изолир", "по одной", "одну переменн",
        ),
        "A rollback or safety net is considered before changing state": (
            "rollback", "roll back", "revert", "undo", "safety net",
            "backup", "snapshot", "canary", "feature flag", "dry run",
            "откат", "возврат", "резервн",
        ),
        "The root cause is addressed, not just the symptom": (
            "root cause", "underlying", "real cause", "not just the symptom",
            "fix the cause", "permanently fix",
            "первопричин", "истинная причина", "причина а не симптом",
        ),
    },
    "data_analysis": {
        "The question is framed before any querying": (
            "question", "frame", "framing", "goal of the analysis",
            "business question", "what we want to know",
            "вопрос", "цель анализ", "задача",
        ),
        "Metric definitions are explicit and consistent": (
            "metric", "definition", "define", "kpi", "measure",
            "numerator", "denominator", "conversion rate", "retention", "ctr",
            "метрик", "определен", "показатель",
        ),
        "Segmentation is considered and justified": (
            "segment", "segmentation", "cohort", "group", "slice",
            "breakdown", "split", "dimension",
            "сегмент", "когорт", "разрез", "группир",
        ),
        "Confounders and data-quality caveats are noted": (
            "confounder", "confounding", "caveat", "data quality", "noise",
            "bias", "selection bias", "missing data", "outlier", "seasonality",
            "искажающ", "качество данных", "пропуски", "выбросы",
        ),
        "The conclusion is actionable, not just descriptive": (
            "actionable", "recommend", "recommendation", "next step",
            "so we should", "implies", "do next", "decision",
            "действ", "рекомендац", "следующий шаг",
        ),
    },
    "behavioral_case": {
        "Situation is concrete and specific": (
            "situation", "context", "when i", "at the time", "specifically",
            "in particular", "concrete",
            "ситуац", "контекст", "конкретно",
        ),
        "Task and your role are clear": (
            "task", "my role", "i was responsible", "my responsibility",
            "i needed to", "goal", "ownership",
            "задача", "моя роль", "ответствен",
        ),
        "Action describes what YOU did, with specifics": (
            "i implemented", "i built", "i designed", "i led", "i drove",
            "i decided", "i introduced", "i negotiated", "i wrote",
            "i refactored", "i proposed", "step by step",
            "я реализовал", "я сделал", "я предложил", "я руководил",
        ),
        "Result is quantified where possible": (
            "result", "outcome", "%", "percent", "x faster", "reduced by",
            "saved", "increased", "delivered", "shipped", "launched",
            "итог", "результат", "вырос", "снизил",
        ),
        "Ownership and learning are evident": (
            "i learned", "lesson", "takeaway", "what i learned",
            "retrospective", "reflect", "i took ownership", "i owned",
            "вывод", "урок", "осознал", "рефлекс",
        ),
    },
    "take_home_brief": {
        "Scope is clarified before building": (
            "scope", "clarify", "clarified", "in scope", "out of scope",
            "requirements", "границы", "область", "скоуп", "уточнил",
        ),
        "Assumptions are documented": (
            "assume", "assumption", "documented", "i assumed", "given that",
            "предполож", "допущен",
        ),
        "The core happy path is delivered first": (
            "happy path", "core path", "mvp", "minimum viable", "first",
            "start with", "primary flow", "main case",
            "базовый сценарий", "основной путь",
        ),
        "Tests and edge cases are addressed": (
            "test", "tests", "testing", "unit test", "edge case",
            "corner case", "coverage", "tdd", "тест", "пограничн",
        ),
        "Trade-offs and next steps are written up": (
            "tradeoff", "trade-off", "next step", "follow up", "follow-up",
            "what i would do next", "limitations", "future work",
            "компромисс", "следующий шаг", "ограничен",
        ),
    },
}


_COACHING_NOTE = (
    "overall below 50 — revisit the rubric and address the criteria listed under improvements"
)
_EMPTY_ANSWER_NOTE = "answer is empty — add concrete detail for each criterion"

# Предел показываемых токенов в reason (без подстрок ответа — только имена токенов).
_REASON_TOKEN_LIMIT = 4


@dataclass(slots=True)
class CriterionScore:
    """Оценка одного критерия рубрики."""

    criterion: str
    score: int  # 0..3
    level: str  # none|low|medium|high
    reason: str  # имена токенов, не подстроки ответа

    def as_dict(self) -> dict[str, Any]:
        return {
            "criterion": self.criterion,
            "score": self.score,
            "level": self.level,
            "reason": self.reason,
        }


@dataclass(slots=True)
class RubricScoreReport:
    """Per-criterion rubric scoring отчёт по ответу на practice-кейс."""

    criterion_scores: list[CriterionScore] = field(default_factory=list)
    overall_score: float = 0.0  # 0..100
    grade: str = "weak"
    feedback: dict[str, list[str]] = field(default_factory=dict)
    rubric_version: str = RUBRIC_VERSION
    requires_human_review: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "criterion_scores": [c.as_dict() for c in self.criterion_scores],
            "overall_score": self.overall_score,
            "grade": self.grade,
            "feedback": {k: list(v) for k, v in (self.feedback or {}).items()},
            "rubric_version": self.rubric_version,
            "requires_human_review": self.requires_human_review,
        }


def _score_to_level(score: int) -> str:
    return _LEVEL_BY_SCORE.get(min(3, max(0, score)), "none")


def _grade_for(overall: float) -> str:
    for threshold, grade in _GRADE_THRESHOLDS:
        if overall >= threshold:
            return grade
    return "weak"


def _count_unique_tokens(answer_cf: str, tokens: tuple[str, ...]) -> tuple[int, list[str]]:
    """Сколько различных токенов из ``tokens`` присутствуют в ответе (casefold)."""
    found: list[str] = []
    for token in tokens:
        token_cf = token.casefold()
        if token_cf and token_cf in answer_cf:
            found.append(token)
    return len(found), found


def score_answer_against_rubric(
    case_type: str,
    answer_text: str,
    rubric: list[str] | None = None,
) -> RubricScoreReport:
    """Оценить ответ per-criterion по стабильной рубрике ``case_type``.

    ``rubric`` по умолчанию = ``build_rubric(case_type)``. Для каждого критерия
    считаем уникальные маркерные термины; ``score = min(3, count)``; ``overall``
    = ``round(sum/count * 100 / 3, 1)`` (count = число критериев). ``reason``
    ссылается на имена токенов (ПДн ответа не утекает в JSON).
    """
    criteria = rubric if rubric is not None else build_rubric(case_type)
    answer_cf = (answer_text or "").casefold()
    tokens_by_criterion = _RUBRIC_TOKENS.get(case_type, {})

    criterion_scores: list[CriterionScore] = []
    for criterion in criteria:
        tokens = tokens_by_criterion.get(criterion, ())
        count, found = _count_unique_tokens(answer_cf, tokens)
        score = min(3, count)
        level = _score_to_level(score)
        if score == 0:
            reason = f"no marker terms for '{criterion}'"
        else:
            shown = ", ".join(found[:_REASON_TOKEN_LIMIT])
            reason = f"matched {count} marker term(s): {shown}"
        criterion_scores.append(
            CriterionScore(criterion=criterion, score=score, level=level, reason=reason)
        )

    n = len(criterion_scores)
    raw_sum = sum(c.score for c in criterion_scores)
    overall = round((raw_sum / n * 100.0 / 3.0), 1) if n else 0.0
    grade = _grade_for(overall)

    strengths = [c.criterion for c in criterion_scores if c.level == "high"]
    improvements = [
        f"Address: {c.criterion}" for c in criterion_scores if c.level in ("none", "low")
    ]
    issues: list[str] = []
    if not (answer_text or "").strip():
        issues.append(_EMPTY_ANSWER_NOTE)
    if overall < 50.0:
        issues.append(_COACHING_NOTE)

    return RubricScoreReport(
        criterion_scores=criterion_scores,
        overall_score=overall,
        grade=grade,
        feedback={"strengths": strengths, "improvements": improvements, "issues": issues},
        rubric_version=RUBRIC_VERSION,
        requires_human_review=True,
    )


def build_cross_session_progress(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    """Агрегировать прогресс по попыткам (created_at asc — ответственность репозитория).

    Пусто → ``{total_attempts:0, reason:"no attempts yet", overall:None,
    per_criterion:[]}`` (``overall:None`` для схемы ``OverallProgressResponse | None``).
    Иначе: ``overall{first,last,best,improvement,trend}``,
    ``per_criterion[{criterion,first,last,best,improvement}]`` (0..3, best = max по
    всем попыткам). trend: improving (delta>1.0) / declining (<-1.0) / stable.
    Backward-looking snapshot — **без** forecast/predicted/probability.
    """
    if not attempts:
        return {
            "total_attempts": 0,
            "reason": "no attempts yet",
            "overall": None,
            "per_criterion": [],
        }

    def _overall(a: dict[str, Any]) -> float:
        try:
            return float(a.get("overall_score") or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _scores(a: dict[str, Any]) -> dict[str, int]:
        out: dict[str, int] = {}
        for c in a.get("criterion_scores_json") or a.get("criterion_scores") or []:
            try:
                out[str(c.get("criterion"))] = int(c.get("score") or 0)
            except (TypeError, ValueError):
                out[str(c.get("criterion"))] = 0
        return out

    first = attempts[0]
    last = attempts[-1]
    overalls = [_overall(a) for a in attempts]
    first_overall = overalls[0]
    last_overall = overalls[-1]
    best_overall = max(overalls) if overalls else 0.0
    improvement = round(last_overall - first_overall, 1)
    if improvement > 1.0:
        trend = "improving"
    elif improvement < -1.0:
        trend = "declining"
    else:
        trend = "stable"

    last_scores = _scores(last)
    first_scores = _scores(first)
    per_criterion: list[dict[str, Any]] = []
    for criterion, last_score in last_scores.items():
        first_score = first_scores.get(criterion, 0)
        best = last_score
        for a in attempts:
            best = max(best, _scores(a).get(criterion, 0))
        per_criterion.append(
            {
                "criterion": criterion,
                "first": first_score,
                "last": last_score,
                "best": best,
                "improvement": last_score - first_score,
            }
        )

    return {
        "total_attempts": len(attempts),
        "overall": {
            "first": first_overall,
            "last": last_overall,
            "best": best_overall,
            "improvement": improvement,
            "trend": trend,
        },
        "per_criterion": per_criterion,
    }


def assert_scoring_deterministic(case_type: str, answer_text: str, runs: int = 3) -> bool:
    """Guard: повторные вызовы дают идентичный отчёт (для тестов)."""
    if case_type not in STABLE_CASE_TYPES:
        return False
    baseline = score_answer_against_rubric(case_type, answer_text).as_dict()
    for _ in range(max(1, runs) - 1):
        if score_answer_against_rubric(case_type, answer_text).as_dict() != baseline:
            return False
    return True