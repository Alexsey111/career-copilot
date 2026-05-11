from __future__ import annotations

from app.domain.normalized_signals import SignalType

# Calibration profiles for different signal types
# These control how raw scores are adjusted to normalized distributions
CALIBRATION_PROFILES = {
    SignalType.COVERAGE: {
        "low_boost": 1.2,      # Boost low scores (< 0.3) by this factor
        "high_damping": 0.95,  # Dampen high scores (> 0.8) by this factor
        "mid_range": (0.3, 0.8),  # Range where no adjustment is made
    },
    SignalType.EVIDENCE: {
        "quality_adjustment": 0.9,  # Base adjustment factor
        "baseline_offset": 0.05,    # Add this to adjusted score
        "use_quality_distribution": True,  # If metadata has quality_distribution, skip adjustment
    },
    SignalType.ATS: {
        "keyword_penalty": 0.9,  # Reduce keyword matching scores
    },
    SignalType.INTERVIEW: {
        "low_boost": 1.1,      # Boost low scores (< 0.4)
        "high_damping": 0.95,  # Dampen high scores
        "threshold": 0.4,      # Boost threshold
    },
    SignalType.QUALITY: {
        "composite_factor": 0.85,  # Adjustment factor for composite scores
        "baseline_offset": 0.075,  # Add this to adjusted score
    },
    SignalType.READINESS: {
        "behavioral_factor": 0.9,  # Adjustment for behavioral signals
    },
}

# Calibration versioning
CURRENT_CALIBRATION_VERSION = "v1.0"

# Historical calibration versions for reproducibility
CALIBRATION_VERSIONS = {
    "v1.0": CALIBRATION_PROFILES,
    # Future versions can be added here
}