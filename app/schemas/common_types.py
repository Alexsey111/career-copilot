# app\schemas\common_types.py

from typing import Literal

FactStatus = Literal[
    "confirmed",
    "needs_confirmation",
    "inferred",
]

RequirementScope = Literal[
    "must_have",
    "nice_to_have",
]

DocumentKind = Literal[
    "resume",
    "cover_letter",
]

ContentSource = Literal[
    "extracted",
    "ai_generated",
    "user_edited",
    "hybrid",
]

WarningSeverity = Literal[
    "info",
    "warning",
    "critical",
]