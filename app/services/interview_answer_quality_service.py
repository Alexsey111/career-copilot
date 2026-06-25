# app\services\interview_answer_quality_service.py

from __future__ import annotations

from typing import Any, Mapping

from app.domain.interview_answer_quality import (
    InterviewAnswerQualityIssue,
    InterviewAnswerQualityReport,
)


PLACEHOLDER_PATTERNS = [
    "дособрать задачу",
    "уточнить личный вклад",
    "добавить проверяемый результат",
    "есть релевантный факт",
]


class InterviewAnswerQualityService:
    def evaluate(self, answer: Mapping[str, Any]) -> InterviewAnswerQualityReport:
        metrics = {
            "star_completeness": self._score_star_completeness(answer, max_score=30),
            "evidence_usage": self._score_evidence_usage(answer, max_score=25),
            "specificity": self._score_specificity(answer, max_score=20),
            "overclaim_safety": self._score_overclaim_safety(answer, max_score=15),
            "readiness": self._score_readiness(answer, max_score=10),
        }

        issues = self._issues(answer, metrics)
        score = max(0, min(100, sum(metrics.values())))

        return InterviewAnswerQualityReport(
            score=score,
            grade=self._grade(score),
            metrics=metrics,
            strengths=self._strengths(metrics, answer),
            improvements=self._improvements(issues, score),
            issues=issues,
        )

    def _score_star_completeness(
        self,
        answer: Mapping[str, Any],
        *,
        max_score: int,
    ) -> int:
        fields = ["situation", "task", "action", "result"]
        filled = [
            field
            for field in fields
            if str(answer.get(field) or "").strip()
            and "пока нет достаточно" not in str(answer.get(field) or "").lower()
            and "добавить подтверждённый" not in str(answer.get(field) or "").lower()
        ]
        score = round(max_score * len(filled) / len(fields))
        if self._has_placeholder_answer(answer):
            return min(score, round(max_score * 0.5))
        return score

    def _score_evidence_usage(
        self,
        answer: Mapping[str, Any],
        *,
        max_score: int,
    ) -> int:
        if answer.get("source_evidence_id"):
            return max_score

        grounding_status = str(answer.get("grounding_status") or "").lower()
        if grounding_status == "partial_evidence":
            return round(max_score * 0.55)

        return 0

    def _score_specificity(
        self,
        answer: Mapping[str, Any],
        *,
        max_score: int,
    ) -> int:
        text = self._answer_text(answer).lower()
        score = 0

        if any(char.isdigit() for char in text):
            score += 8

        if len(text.split()) >= 35:
            score += 6

        if answer.get("tech_stack"):
            score += 3

        if answer.get("source_title"):
            score += 3

        return min(max_score, score)

    def _score_overclaim_safety(
        self,
        answer: Mapping[str, Any],
        *,
        max_score: int,
    ) -> int:
        if answer.get("requires_human_review") is not True:
            return 0

        text = self._answer_text(answer).lower()
        risky = [
            "точно владею",
            "эксперт",
            "гарантирую",
            "полностью отвечал",
            "самостоятельно сделал",
        ]
        if any(item in text for item in risky):
            return round(max_score * 0.35)

        return max_score

    def _score_readiness(
        self,
        answer: Mapping[str, Any],
        *,
        max_score: int,
    ) -> int:
        status = str(answer.get("grounding_status") or "").lower()
        if status == "grounded":
            return max_score
        if status == "partial_evidence":
            return round(max_score * 0.6)
        if status == "needs_confirmation":
            return round(max_score * 0.35)
        return 0

    def _issues(
        self,
        answer: Mapping[str, Any],
        metrics: dict[str, int],
    ) -> list[InterviewAnswerQualityIssue]:
        issues: list[InterviewAnswerQualityIssue] = []

        if metrics["evidence_usage"] == 0:
            issues.append(
                InterviewAnswerQualityIssue(
                    code="missing_evidence",
                    severity="warning",
                    message="К ответу не привязано подтверждённое доказательство.",
                    metric="evidence_usage",
                )
            )

        if metrics["star_completeness"] < 20:
            issues.append(
                InterviewAnswerQualityIssue(
                    code="incomplete_star",
                    severity="warning",
                    message="Ответу не хватает полной STAR-структуры.",
                    metric="star_completeness",
                )
            )

        if metrics["overclaim_safety"] < 15:
            issues.append(
                InterviewAnswerQualityIssue(
                    code="possible_overclaim",
                    severity="risk",
                    message="В ответе есть риск неподтверждённых сильных утверждений.",
                    metric="overclaim_safety",
                )
            )

        return issues

    def _strengths(
        self,
        metrics: dict[str, int],
        answer: Mapping[str, Any],
    ) -> list[str]:
        strengths: list[str] = []

        if metrics["evidence_usage"] >= 20:
            strengths.append("Ответ связан с подтверждённым доказательством.")

        if metrics["star_completeness"] >= 25:
            strengths.append("Ответ хорошо покрывает STAR-структуру.")

        if metrics["overclaim_safety"] == 15:
            strengths.append("Ответ не содержит явных неподтверждённых claims.")

        return strengths

    def _improvements(
        self,
        issues: list[InterviewAnswerQualityIssue],
        score: int,
    ) -> list[str]:
        improvements = [issue.message for issue in issues]

        if score < 70 and not improvements:
            improvements.append("Усилить доказательность, конкретику и STAR-структуру ответа.")

        return improvements

    def _grade(self, score: int) -> str:
        if score >= 85:
            return "excellent"
        if score >= 70:
            return "good"
        if score >= 50:
            return "needs_work"
        return "weak"

    def _answer_text(self, answer: Mapping[str, Any]) -> str:
        return " ".join(
            str(answer.get(field) or "")
            for field in ["situation", "task", "action", "result", "draft_text"]
        )

    def _has_placeholder_answer(self, answer: Mapping[str, Any]) -> bool:
        text = self._answer_text(answer).lower()
        return any(pattern in text for pattern in PLACEHOLDER_PATTERNS)
