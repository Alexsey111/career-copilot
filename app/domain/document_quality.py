# app\domain\document_quality.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class DocumentQualityIssue:
    code: str
    severity: str
    message: str
    metric: str | None = None


@dataclass(slots=True)
class DocumentQualityRecommendation:
    code: str
    title: str
    why: str
    actions: list[str] = field(default_factory=list)
    metric: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    impact: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ImprovementRoadmapStep:
    order: int
    title: str
    expected_gain: int
    recommendation_code: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "order": self.order,
            "title": self.title,
            "expected_gain": self.expected_gain,
        }


@dataclass(slots=True)
class ImprovementRoadmap:
    current_score: int
    projected_score: int
    steps: list[ImprovementRoadmapStep] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "current_score": self.current_score,
            "projected_score": self.projected_score,
            "steps": [step.as_dict() for step in self.steps],
        }


@dataclass(slots=True)
class DocumentQualityScoreItem:
    code: str
    label: str
    score: int
    max_score: int
    missing_points: int


@dataclass(slots=True)
class DocumentQualityReport:
    document_kind: str
    score: int
    grade: str
    metrics: dict[str, int] = field(default_factory=dict)
    strengths: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)
    issues: list[DocumentQualityIssue] = field(default_factory=list)
    recommendations: list[DocumentQualityRecommendation] = field(default_factory=list)
    score_breakdown: list[DocumentQualityScoreItem] = field(default_factory=list)
    roadmap: ImprovementRoadmap | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "document_kind": self.document_kind,
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
            "recommendations": [
                {
                    "code": item.code,
                    "title": item.title,
                    "why": item.why,
                    "actions": item.actions,
                    "metric": item.metric,
                    "details": item.details,
                    "impact": item.impact,
                }
                for item in self.recommendations
            ],
            "score_breakdown": [
                {
                    "code": item.code,
                    "label": item.label,
                    "score": item.score,
                    "max_score": item.max_score,
                    "missing_points": item.missing_points,
                }
                for item in self.score_breakdown
            ],
            "roadmap": self.roadmap.as_dict() if self.roadmap else None,
        }
