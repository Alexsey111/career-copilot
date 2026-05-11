from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SignalType(Enum):
    """Canonical signal types for document evaluation."""
    COVERAGE = "coverage"
    EVIDENCE = "evidence"
    ATS = "ats"
    INTERVIEW = "interview"
    QUALITY = "quality"
    READINESS = "readiness"


class SignalTaxonomy(Enum):
    """High-level taxonomy categories for signals."""
    STRUCTURAL = "structural"
    SEMANTIC = "semantic"
    BEHAVIORAL = "behavioral"
    COMPOSITE = "composite"


@dataclass(slots=True)
class NormalizedSignal:
    """Normalized signal with canonical contract."""
    type: SignalType
    taxonomy: SignalTaxonomy
    value: float  # 0.0 - 1.0 normalized score
    confidence: float  # 0.0 - 1.0 confidence in the measurement
    calibrated: bool  # whether this signal has been calibrated
    calibration_version: str = "v1.0"  # Version of calibration applied
    source_signal_ids: list[str] = field(default_factory=list)  # IDs of source signals for lineage

    @property
    def is_valid(self) -> bool:
        """Check if signal values are in valid ranges."""
        return (
            0.0 <= self.value <= 1.0 and
            0.0 <= self.confidence <= 1.0
        )

    @property
    def effective_score(self) -> float:
        """Get score weighted by confidence."""
        return self.value * self.confidence

    @staticmethod
    def taxonomy_for_type(signal_type: SignalType) -> SignalTaxonomy:
        """Map signal type to high-level taxonomy."""
        mapping = {
            SignalType.COVERAGE: SignalTaxonomy.STRUCTURAL,
            SignalType.ATS: SignalTaxonomy.STRUCTURAL,
            SignalType.EVIDENCE: SignalTaxonomy.SEMANTIC,
            SignalType.INTERVIEW: SignalTaxonomy.SEMANTIC,
            SignalType.QUALITY: SignalTaxonomy.COMPOSITE,
            SignalType.READINESS: SignalTaxonomy.BEHAVIORAL,
        }
        return mapping.get(signal_type, SignalTaxonomy.COMPOSITE)
