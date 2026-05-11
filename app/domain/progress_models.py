from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class ReadinessSnapshot:
    snapshot_id: str

    overall_score: float

    ats_score: float
    evidence_score: float
    interview_score: float
    coverage_score: float
    quality_score: float

    created_at: datetime
    calibration_version: str = "v1.0"  # Version of calibration used for scoring


@dataclass(slots=True)
class ReadinessDelta:
    previous_score: float
    current_score: float
    delta: float

    improved_areas: list[str]
    regressed_areas: list[str]

    blocking_issues_resolved: list[str]
    new_blocking_issues: list[str]
