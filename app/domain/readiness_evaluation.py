# app\domain\readiness_evaluation.py

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ReadinessLevel(str, Enum):
    READY = "ready"
    NEEDS_WORK = "needs_work"
    NOT_READY = "not_ready"


@dataclass(slots=True)
class ComponentScore:
    name: str
    score: float
    weight: float
    explanation: str | None = None


@dataclass(slots=True)
class ReadinessEvaluation:
    overall_score: float

    ats_score: float
    evidence_score: float
    coverage_score: float
    quality_score: float

    readiness_level: ReadinessLevel

    scoring_version: str
    prompt_version: str
    extractor_version: str
    model_name: str

    evaluated_at: datetime

    components: list[ComponentScore] = field(default_factory=list)

    blockers: list[str] = field(default_factory=list)

    warnings: list[str] = field(default_factory=list)

    metadata: dict[str, str] = field(default_factory=dict)