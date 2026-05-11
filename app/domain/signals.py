from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class UnifiedSignal:
    """Unified signal for document evaluation across all dimensions."""

    signal_type: str  # coverage | evidence | ats | interview | quality | custom
    score: float  # 0.0 - 1.0
    weight: float  # relative importance in overall scoring
    source: str  # which component generated this signal
    metadata: dict[str, Any] = field(default_factory=dict)
    signal_id: str | None = None  # optional unique identifier for lineage tracking

    @property
    def is_valid(self) -> bool:
        """Check if signal has valid score and weight."""
        return 0.0 <= self.score <= 1.0 and self.weight >= 0.0

    @property
    def weighted_score(self) -> float:
        """Calculate weighted score contribution."""
        return self.score * self.weight