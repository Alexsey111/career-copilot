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
