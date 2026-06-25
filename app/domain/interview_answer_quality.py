# app\domain\interview_answer_quality.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class InterviewAnswerQualityIssue:
    code: str
    severity: str
    message: str
    metric: str | None = None


@dataclass(slots=True)
class InterviewAnswerQualityReport:
    score: int
    grade: str
    metrics: dict[str, int] = field(default_factory=dict)
    strengths: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)
    issues: list[InterviewAnswerQualityIssue] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "grade": self.grade,
            "metrics": self.metrics,
            "strengths": self.strengths,
            "improvements": self.improvements,
            "issues": [
                {
                    "code": issue.code,
                    "severity": issue.severity,
                    "message": issue.message,
                    "metric": issue.metric,
                }
                for issue in self.issues
            ],
        }