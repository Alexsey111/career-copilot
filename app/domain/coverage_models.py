# # app/domain/coverage_models.py

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.constants import CoverageType, EvidenceStrength


@dataclass(slots=True)
class RequirementCoverage:
    """Информация о покрытии одного требования вакансии достижениями."""
    requirement_text: str
    keyword: str | None
    matched_achievement_ids: list[str] = field(default_factory=list)
    coverage_strength: float = 0.0
    coverage_type: CoverageType | str = CoverageType.UNSUPPORTED
    evidence_strength: EvidenceStrength | str = EvidenceStrength.MISSING
    evidence_summary: str | None = None
    priority: str = "important"  # critical | important | optional
