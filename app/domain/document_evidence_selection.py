# app\domain\document_evidence_selection.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class DocumentEvidenceSelection:
    selected_achievements: list[dict[str, Any]] = field(default_factory=list)
    selected_evidence_ids: list[str] = field(default_factory=list)
    evidence_selection_reason: list[dict[str, Any]] = field(default_factory=list)
    vacancy_evidence_alignment: list[dict[str, Any]] = field(default_factory=list)
    top_alignment_evidence: list[dict[str, Any]] = field(default_factory=list)

    def has_evidence(self) -> bool:
        return bool(
            self.selected_evidence_ids
            or self.evidence_selection_reason
            or self.selected_achievements
            or self.top_alignment_evidence
        )