from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.domain.normalized_signals import NormalizedSignal


# Schema versioning constants
SCHEMA_VERSION = "v1.0"
SIGNAL_TAXONOMY_VERSION = "v1.0"


@dataclass(slots=True)
class EvaluationSnapshot:
    """Complete evaluation snapshot with normalized signals and metadata."""
    snapshot_id: str
    created_at: datetime

    readiness_score: float
    calibration_version: str
    schema_version: str = "v1.0"  # Schema version for backward compatibility
    signal_taxonomy_version: str = "v1.0"  # Taxonomy version used for signals

    normalized_signals: list[NormalizedSignal] = field(default_factory=list)

    variance: float = 0.0
    confidence: float = 0.0

    recommendation_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class EvaluationDiff:
    """Difference between two evaluation snapshots."""
    score_delta: float
    confidence_delta: float
    schema_version: str = "v1.0"  # Schema version for this diff

    improved_signals: list[str] = field(default_factory=list)  # Signal types that improved
    regressed_signals: list[str] = field(default_factory=list)  # Signal types that regressed

    newly_blocking: list[str] = field(default_factory=list)  # New blocking issues