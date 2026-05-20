# app\services\document_review_summary_service.py

from __future__ import annotations

from app.services.readiness_gate_service import ReadinessGateService


class DocumentReviewSummaryService:
    def __init__(self, readiness_gate_service: ReadinessGateService | None = None) -> None:
        self.readiness_gate_service = readiness_gate_service or ReadinessGateService()

    def build_summary(self, document) -> dict:
        content = document.content_json or {}
        sections = content.get("sections", {})
        meta = content.get("meta", {})
        readiness = self.readiness_gate_service.evaluate_document_readiness(document)

        selected_achievements = sections.get("selected_achievements", [])
        selected_achievement_ids = self._extract_selected_achievement_ids(
            meta.get("selected_achievement_ids"),
            meta.get("based_on_achievements"),
            selected_achievements,
        )
        selected_evidence_ids = self._extract_selected_evidence_ids(
            meta.get("selected_evidence_ids"),
            meta.get("evidence_selection_reason"),
            selected_achievements,
        )
        evidence_selection_reason = self._extract_evidence_selection_reason(
            meta.get("evidence_selection_reason"),
            selected_achievements,
        )

        return {
            "claims_needing_confirmation": sections.get("claims_needing_confirmation", []),
            "warnings": sections.get("warnings", []),
            "selected_achievements": selected_achievements,
            "selected_achievement_ids": selected_achievement_ids,
            "selected_evidence_ids": selected_evidence_ids,
            "evidence_selection_reason": evidence_selection_reason,
            "matched_keywords": sections.get("matched_keywords", []),
            "missing_keywords": sections.get("missing_keywords", []),
            "selection_rationale": sections.get("selection_rationale", []),
            "readiness": {
                "ready": readiness.ready,
                "blockers": readiness.blockers,
                "warnings": readiness.warnings,
                "score": readiness.score,
            },
        }

    def _extract_selected_evidence_ids(
        self,
        selected_evidence_ids,
        evidence_selection_reason,
        selected_achievements: list[dict],
    ) -> list[str]:
        ids: list[str] = []

        for value in selected_evidence_ids or []:
            normalized = str(value or "").strip()
            if normalized:
                ids.append(normalized)

        if ids:
            return ids

        for item in evidence_selection_reason or []:
            if not isinstance(item, dict):
                continue
            normalized = str(item.get("evidence_id") or "").strip()
            if normalized:
                ids.append(normalized)

        if ids:
            return ids

        return ids

    def _extract_selected_achievement_ids(
        self,
        selected_achievement_ids,
        based_on_achievements,
        selected_achievements: list[dict],
    ) -> list[str]:
        ids: list[str] = []

        for value in selected_achievement_ids or []:
            normalized = str(value or "").strip()
            if normalized:
                ids.append(normalized)

        if ids:
            return ids

        for item in based_on_achievements or []:
            normalized = str(item or "").strip()
            if normalized:
                ids.append(normalized)

        if ids:
            return ids

        for item in selected_achievements or []:
            normalized = str(item.get("id") or "").strip()
            if normalized:
                ids.append(normalized)

        return ids

    def _extract_evidence_selection_reason(
        self,
        raw_reasons,
        selected_achievements: list[dict],
    ) -> list[dict]:
        if raw_reasons:
            return list(raw_reasons)

        reasons: list[dict] = []
        for item in selected_achievements or []:
            reasons.append(
                {
                    "item": item.get("title"),
                    "type": "achievement",
                    "reason": item.get("reason"),
                }
            )
        return reasons
