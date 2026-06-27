# app\services\document_evidence_selection_service.py

from __future__ import annotations

import re
from typing import Any

from app.domain.document_evidence_selection import DocumentEvidenceSelection


class DocumentEvidenceSelectionService:
    def build_from_document_parts(
        self,
        *,
        selected_achievements: list[dict[str, Any]] | None = None,
        selected_evidence_ids: list[str] | None = None,
        evidence_selection_reason: list[dict[str, Any]] | None = None,
        vacancy_evidence_alignment: list[dict[str, Any]] | None = None,
        top_alignment_evidence: list[dict[str, Any]] | None = None,
    ) -> DocumentEvidenceSelection:
        achievements = self._dedupe_dicts_by_id_or_title(selected_achievements or [])
        evidence_ids = self._dedupe_strings(selected_evidence_ids or [])
        reasons = self._dedupe_reason_items(evidence_selection_reason or [])

        if not evidence_ids:
            evidence_ids = self._extract_evidence_ids_from_reasons(reasons)

        if not evidence_ids:
            evidence_ids = self._extract_evidence_ids_from_achievements(achievements)

        return DocumentEvidenceSelection(
            selected_achievements=achievements,
            selected_evidence_ids=evidence_ids,
            evidence_selection_reason=reasons,
            vacancy_evidence_alignment=list(vacancy_evidence_alignment or []),
            top_alignment_evidence=list(top_alignment_evidence or []),
        )

    def _dedupe_strings(self, values: list[Any]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()

        for value in values:
            cleaned = str(value or "").strip()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            result.append(cleaned)

        return result

    def _dedupe_dicts_by_id_or_title(
        self,
        values: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        seen: set[str] = set()

        for item in values:
            if not isinstance(item, dict):
                continue

            key = str(item.get("id") or item.get("title") or "").strip().casefold()
            if not key or key in seen:
                continue

            seen.add(key)
            result.append(item)

        return result

    def _dedupe_reason_items(
        self,
        values: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        seen: set[str] = set()

        for item in values:
            if not isinstance(item, dict):
                continue

            evidence_id = str(item.get("evidence_id") or "").strip()
            title = re.sub(r"\s+", " ", str(item.get("title") or item.get("item") or "").strip())
            reason = re.sub(r"\s+", " ", str(item.get("reason") or "").strip())
            key = "|".join([evidence_id, title.casefold(), reason.casefold()])

            if key in seen:
                continue

            seen.add(key)
            result.append(item)

        return result

    def _extract_evidence_ids_from_reasons(
        self,
        reasons: list[dict[str, Any]],
    ) -> list[str]:
        return self._dedupe_strings(
            [
                str(item.get("evidence_id") or "").strip()
                for item in reasons
                if isinstance(item, dict)
            ]
        )

    def _extract_evidence_ids_from_achievements(
        self,
        achievements: list[dict[str, Any]],
    ) -> list[str]:
        return self._dedupe_strings(
            [
                str(item.get("id") or "").strip()
                for item in achievements
                if isinstance(item, dict)
            ]
        )