# app\domain\contribution.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class NormalizedContributionSignal:
    """Candidate-neutral contribution signal extracted from source text."""

    title: str
    contribution_type: str
    source_text: str
    skills: list[str] = field(default_factory=list)
    confidence: str = "medium"
    ownership_confidence: str = "low"
    requires_confirmation: bool = True
    source_layer: str = "generic_extraction"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReviewedCandidateOwnership:
    """Review boundary between extracted facts and candidate-owned claims."""

    signal: NormalizedContributionSignal
    ownership_status: str = "needs_review"
    ownership_confidence: str = "low"
    requires_confirmation: bool = True
    fact_status: str = "needs_confirmation"
    reviewer_note: str = (
        "Extracted as a normalized contribution signal; candidate ownership "
        "must be reviewed before strong use in documents."
    )
