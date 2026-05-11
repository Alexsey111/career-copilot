from __future__ import annotations

from enum import StrEnum, auto


class CoverageType(StrEnum):
    """Типы покрытия требований."""
    DIRECT = auto()
    PARTIAL = auto()
    INFERRED = auto()
    UNSUPPORTED = auto()


class EvidenceStrength(StrEnum):
    """Сила доказательств."""
    STRONG = auto()
    MODERATE = auto()
    WEAK = auto()
    MISSING = auto()


class Priority(StrEnum):
    """Приоритет требований."""
    CRITICAL = auto()
    IMPORTANT = auto()
    OPTIONAL = auto()


class FactStatus(StrEnum):
    """Статус подтверждения факта."""
    CONFIRMED = auto()
    PENDING = auto()
    REJECTED = auto()


class CheckSeverity(StrEnum):
    """Серьёзность результата проверки."""
    INFO = auto()
    WARNING = auto()
    CRITICAL = auto()


class QualityLabel(StrEnum):
    """Метки качества доказательств."""
    EXCELLENT = auto()
    GOOD = auto()
    ACCEPTABLE = auto()
    WEAK = auto()
    MISSING = auto()


# Пороговые значения для scoring
COVERAGE_STRENGTH_DIRECT_THRESHOLD = 0.75
COVERAGE_STRENGTH_PARTIAL_THRESHOLD = 0.30
EVIDENCE_SCORE_EXCELLENT_THRESHOLD = 0.7
EVIDENCE_SCORE_GOOD_THRESHOLD = 0.5
EVIDENCE_SCORE_ACCEPTABLE_THRESHOLD = 0.3

# Стандартные пороги для всех scoring systems
SIGNAL_USABLE_THRESHOLD = 0.3
SIGNAL_ACCEPTABLE_THRESHOLD = 0.5
SIGNAL_STRONG_THRESHOLD = 0.7
SIGNAL_EXCELLENT_THRESHOLD = 0.9

# Веса приоритетов для ATS match score
PRIORITY_WEIGHTS = {
    Priority.CRITICAL: 1.0,
    Priority.IMPORTANT: 0.7,
    Priority.OPTIONAL: 0.3,
}

# Generic phrases blacklist для evidence detection
GENERIC_PHRASES = [
    "participated",
    "helped",
    "assisted",
    "worked on",
    "involved in",
    "took part",
    "contributed to",
]

# Patterns для generic detection (regex)
GENERIC_PATTERNS = [
    r"\bparticipated\b",
    r"\bhelped\b",
    r"\bassisted\b",
    r"\bworked on\b",
    r"\binvolved in\b",
    r"\btake part\b",
    r"\bcontributed to\b",
    r"\bwere responsible for\b",
    r"\bwas responsible for\b",
]


class CheckCode(StrEnum):
    """Коды проверок для детерминированных eval checks."""
    NO_EMPTY_COVERAGE = auto()
    NO_UNSUPPORTED_CRITICAL = auto()
    NO_MISSING_EVIDENCE = auto()
    NO_FAKE_DIRECT = auto()
    NO_SCORE_INFLATION = auto()
    NO_GENERIC_EVIDENCE = auto()
    SPECIFICITY = auto()
    STAR_COMPLETENESS = auto()
    EVIDENCE_QUALITY = auto()
    GENERIC_WORDING = auto()


class ReviewReasonCode(StrEnum):
    """Коды причин для review comments."""
    MISSING_CRITICAL_REQUIREMENT = auto()
    WEAK_EVIDENCE = auto()
    GENERIC_PHRASE_DETECTED = auto()
    INCOMPLETE_STAR = auto()
    LACK_OF_METRICS = auto()
    KEYWORD_LOSS = auto()
    HALLUCINATED_METRIC = auto()
    FABRICATED_EXPERIENCE = auto()
    UNSAFE_ENHANCEMENT = auto()
    EMPTY_RENDERING = auto()
