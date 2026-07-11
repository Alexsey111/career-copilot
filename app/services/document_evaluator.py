# app/services/document_evaluator.py

from __future__ import annotations

import re
from typing import Any

from app.domain.trace_models import (
    AIAuditMetadata,
    DeterministicCheckResult,
    DocumentEvaluationReport,
    GenerationTrace,
)


# Паттерны «число + единица» для детекции метрик в тексте.
# Каждый кортеж: (regex, фиксированная единица или None → взять из группы 2).
_METRIC_TOKEN_PATTERNS: list[tuple[re.Pattern[str], str | None]] = [
    (re.compile(r"\$\s*(\d+(?:[.,]\d+)?)", re.I), "$"),
    (re.compile(r"(\d+(?:[.,]\d+)?)\s*%", re.I), "%"),
    (re.compile(r"в\s+(\d+(?:[.,]\d+)?)\s*раз(?:а|ами)?", re.I), "раз"),
    (re.compile(r"(\d+(?:[.,]\d+)?)\s*раз(?:а|ами)?", re.I), "раз"),
    (re.compile(r"(\d+(?:[.,]\d+)?)\s*х\b", re.I), "x"),
    (re.compile(r"(\d+(?:[.,]\d+)?)\s*(тыс|млн|million|billion)\b", re.I), None),
    (
        re.compile(
            r"(?:увеличил|сократил|рост|снизил|вырос)\S*\s+(?:на\s+)?(\d+(?:[.,]\d+)?)\s*%",
            re.I,
        ),
        "%",
    ),
]


def _normalize_number(raw: str) -> str:
    return raw.replace(",", ".").strip()


def _extract_metrics(text: str) -> set[tuple[str, str]]:
    """Извлекает из текста множество нормализованных метрик (number, unit)."""
    if not text:
        return set()
    metrics: set[tuple[str, str]] = set()
    for pattern, fixed_unit in _METRIC_TOKEN_PATTERNS:
        for match in pattern.finditer(text):
            number = _normalize_number(match.group(1))
            if not number:
                continue
            unit = fixed_unit if fixed_unit else (match.group(2) or "").lower()
            metrics.add((number, unit))
    return metrics


def extract_baseline_metrics(
    achievements: list[dict[str, Any]] | None,
    experience_items: list[dict[str, Any]] | None = None,
) -> set[tuple[str, str]]:
    """Подтверждённые метрики из достижений/опыта — baseline для narrative fact-check.

    Только confirmed/user_provided достижения — это «источник правды» для метрик.
    Метрики из enhanced AI-текста, отсутствующие в baseline, считаются выдуманными.
    """
    texts: list[str] = []
    for achievement in achievements or []:
        if str(achievement.get("fact_status", "")).lower() in {"confirmed", "user_provided"}:
            texts.append(
                f"{achievement.get('result', '') or ''} {achievement.get('metric_text', '') or ''}"
            )
    for exp in experience_items or []:
        texts.append(exp.get("description_raw", "") or "")
    metrics: set[tuple[str, str]] = set()
    for text in texts:
        metrics |= _extract_metrics(text)
    return metrics


class DocumentEvaluator:
    """Детерминированная валидация документов на hallucinations и safety."""

    def __init__(
        self,
        *,
        original_content: dict[str, Any] | None = None,
        generated_content: dict[str, Any],
    ):
        self.original = original_content or {}
        self.generated = generated_content
        self.checks: list[DeterministicCheckResult] = []

    def check_no_hallucinated_metrics(self) -> None:
        """Проверка: нет ли выдуманных метрик в result/metric_text."""
        sections = self.generated.get("sections", {})
        achievements = sections.get("selected_achievements", [])

        for achievement in achievements:
            result = achievement.get("result", "") or ""
            metric_text = achievement.get("metric_text", "") or ""
            fact_status = achievement.get("fact_status", "needs_confirmation")

            combined = f"{result} {metric_text}".lower()

            # Ищем паттерны метрик
            metric_patterns = [
                r"\d+%",
                r"\$\d+",
                r"\d+\s*(million|billion|тыс|млн)",
                r"увеличил(?:ось|а|ли)?\s+на\s+\d+%",
                r"сократил(?:ось|а|ли)?\s+на\s+\d+%",
                r"рост\s+на\s+\d+%",
            ]

            has_metrics = any(
                re.search(pattern, combined) for pattern in metric_patterns
            )

            if has_metrics and fact_status != "confirmed":
                self.checks.append(DeterministicCheckResult(
                    passed=False,
                    check_name="no_hallucinated_metrics",
                    message=(
                        f"Метрика найдена без подтверждения: "
                        f"achievement '{achievement.get('title', 'unknown')}'"
                    ),
                    severity="critical",
                ))
            else:
                self.checks.append(DeterministicCheckResult(
                    passed=True,
                    check_name="no_hallucinated_metrics",
                    message="Нет неподтверждённых метрик",
                    severity="info",
                ))

    def check_no_hallucinated_narrative_metrics(self) -> None:
        """Проверка: нет ли выдуманных метрик в AI-enhanced тексте (rendered_text/fit_summary).

        Baseline — подтверждённые метрики из original_content['baseline_metrics']
        (построенные `extract_baseline_metrics` из confirmed-достижений/опыта).
        Если baseline пуст — пропускаем (нельзя блокировать, когда у пользователя
        вообще нет подтверждённых метрик). Иначе любая метрика в enhanced-тексте,
        отсутствующая в baseline, считается hallucinated (critical).
        """
        baseline = set(self.original.get("baseline_metrics", []) or [])

        texts: list[str] = []
        rendered = self.generated.get("rendered_text", "")
        if isinstance(rendered, str) and rendered:
            texts.append(rendered)
        fit_summary = self.generated.get("sections", {}).get("fit_summary")
        if isinstance(fit_summary, str) and fit_summary:
            texts.append(fit_summary)

        if not baseline:
            self.checks.append(DeterministicCheckResult(
                passed=True,
                check_name="no_hallucinated_narrative_metrics",
                message="baseline metrics пуст — narrative hallucinated-metrics check пропущен",
                severity="info",
            ))
            return

        enhanced_metrics: set[tuple[str, str]] = set()
        for text in texts:
            enhanced_metrics |= _extract_metrics(text)

        invented = enhanced_metrics - baseline
        if invented:
            sample = ", ".join(f"{number}{unit}" for number, unit in sorted(invented)[:5])
            self.checks.append(DeterministicCheckResult(
                passed=False,
                check_name="no_hallucinated_narrative_metrics",
                message=f"Hallucinated метрики в enhanced-тексте: {sample}",
                severity="critical",
            ))
        else:
            self.checks.append(DeterministicCheckResult(
                passed=True,
                check_name="no_hallucinated_narrative_metrics",
                message="Нет hallucinated метрик в enhanced-тексте",
                severity="info",
            ))

    def check_no_fabricated_experience(self) -> None:
        """Проверка: нет ли выдуманных компаний/ролей."""
        original_experience = self.original.get("experience", [])
        generated_experience = self.generated.get("sections", {}).get("experience", [])

        original_companies = {
            exp.get("company", "").lower()
            for exp in original_experience
            if exp.get("company")
        }

        for exp in generated_experience:
            company = exp.get("company", "")
            if company and company.lower() not in original_companies:
                # Новая компания - проверяем fact_status
                self.checks.append(DeterministicCheckResult(
                    passed=False,
                    check_name="no_fabricated_experience",
                    message=f"Новая компания без подтверждения: {company}",
                    severity="warning",
                ))
            else:
                self.checks.append(DeterministicCheckResult(
                    passed=True,
                    check_name="no_fabricated_experience",
                    message="Нет выдуманных компаний",
                    severity="info",
                ))

    def check_no_keyword_loss(self) -> None:
        """Проверка: ключевые слова из vacancy сохранены."""
        original_keywords = set(self.original.get("matched_keywords", []))
        generated_keywords = set(
            self.generated.get("sections", {}).get("matched_keywords", [])
        )

        lost_keywords = original_keywords - generated_keywords

        if lost_keywords:
            self.checks.append(DeterministicCheckResult(
                passed=False,
                check_name="no_keyword_loss",
                message=f"Потеряны ключевые слова: {', '.join(list(lost_keywords)[:5])}",
                severity="warning",
            ))
        else:
            self.checks.append(DeterministicCheckResult(
                passed=True,
                check_name="no_keyword_loss",
                message="Все ключевые слова сохранены",
                severity="info",
            ))

    def check_no_unsafe_enhancement(self) -> None:
        """Проверка: AI enhancement не добавил неподтверждённых фактов."""
        ai_metadata = self.generated.get("meta", {}).get("ai_metadata", {})
        safety_passed = ai_metadata.get("safety_checks_passed", True)

        if not safety_passed:
            self.checks.append(DeterministicCheckResult(
                passed=False,
                check_name="no_unsafe_enhancement",
                message="AI enhancement прошёл без safety checks",
                severity="critical",
            ))
        else:
            self.checks.append(DeterministicCheckResult(
                passed=True,
                check_name="no_unsafe_enhancement",
                message="Safety checks пройдены",
                severity="info",
            ))

    def check_no_empty_rendering(self) -> None:
        """Проверка: документ не пустой после рендеринга."""
        rendered_text = self.generated.get("rendered_text", "")

        if not rendered_text or len(rendered_text.strip()) < 50:
            self.checks.append(DeterministicCheckResult(
                passed=False,
                check_name="no_empty_rendering",
                message="Документ пустой или слишком короткий",
                severity="critical",
            ))
        else:
            self.checks.append(DeterministicCheckResult(
                passed=True,
                check_name="no_empty_rendering",
                message="Документ содержит контент",
                severity="info",
            ))

    def check_ats_keyword_preservation(self) -> None:
        """Проверка: ATS-ключевые слова (hard skills) сохранены."""
        sections = self.generated.get("sections", {})
        generated_skills = set(sections.get("skills", []))

        original_skills = set(self.original.get("sections", {}).get("skills", []))

        if original_skills:
            missing_skills = original_skills - generated_skills
            if missing_skills:
                self.checks.append(DeterministicCheckResult(
                    passed=False,
                    check_name="ats_keyword_preservation",
                    message=f"Потеряны hard skills: {', '.join(list(missing_skills)[:5])}",
                    severity="warning",
                ))
            else:
                self.checks.append(DeterministicCheckResult(
                    passed=True,
                    check_name="ats_keyword_preservation",
                    message="Все ATS-ключевые слова сохранены",
                    severity="info",
                ))

    def evaluate(self) -> DocumentEvaluationReport:
        """Выполняет все проверки и возвращает отчёт."""
        self.check_no_hallucinated_metrics()
        self.check_no_hallucinated_narrative_metrics()
        self.check_no_fabricated_experience()
        self.check_no_keyword_loss()
        self.check_no_unsafe_enhancement()
        self.check_no_empty_rendering()
        self.check_ats_keyword_preservation()

        return DocumentEvaluationReport(
            checks=self.checks,
        )


def evaluate_document(
    *,
    original_content: dict[str, Any] | None = None,
    generated_content: dict[str, Any],
    trace: GenerationTrace | None = None,
    ai_metadata: AIAuditMetadata | None = None,
) -> DocumentEvaluationReport:
    """Утилита для детерминированной оценки документа."""
    evaluator = DocumentEvaluator(
        original_content=original_content,
        generated_content=generated_content,
    )
    report = evaluator.evaluate()
    report.trace = trace
    report.ai_metadata = ai_metadata
    return report
