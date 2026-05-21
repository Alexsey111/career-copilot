# app\services\document_review_summary_service.py

from __future__ import annotations

from app.domain.evidence_confidence import aggregate_evidence_confidence
from app.services.readiness_gate_service import ReadinessGateService


class DocumentReviewSummaryService:
    def __init__(self, readiness_gate_service: ReadinessGateService | None = None) -> None:
        self.readiness_gate_service = readiness_gate_service or ReadinessGateService()

    def build_summary(self, document) -> dict:
        content = document.content_json or {}
        sections = content.get("sections", {})
        meta = content.get("meta", {})
        provenance = dict(content.get("provenance") or meta.get("provenance") or {})
        readiness = self.readiness_gate_service.evaluate_document_readiness(document)

        selected_achievements = sections.get("selected_achievements", [])
        selected_achievement_ids = self._extract_selected_achievement_ids(
            meta.get("selected_achievement_ids"),
            content.get("selected_achievement_ids"),
            meta.get("based_on_achievements"),
            selected_achievements,
        )
        selected_evidence_ids = self._extract_selected_evidence_ids(
            meta.get("selected_evidence_ids"),
            content.get("selected_evidence_ids"),
            meta.get("evidence_selection_reason"),
            selected_achievements,
        )
        evidence_selection_reason = self._extract_evidence_selection_reason(
            meta.get("evidence_selection_reason"),
            selected_achievements,
        )

        provenance.setdefault("source", meta.get("source"))
        provenance.setdefault("generation_mode", content.get("draft_mode"))
        provenance.setdefault("analysis_id", meta.get("based_on_analysis_id"))
        provenance["selected_achievement_ids"] = selected_achievement_ids
        provenance["selected_evidence_ids"] = selected_evidence_ids or selected_achievement_ids
        provenance["evidence_selection_reason"] = evidence_selection_reason
        provenance.setdefault("confidence", meta.get("confidence"))
        confidence_assessment = aggregate_evidence_confidence(
            [
                self._confidence_item_from_selected_achievement(item)
                for item in selected_achievements
                if isinstance(item, dict)
            ]
        )
        provenance.setdefault("confidence", confidence_assessment.confidence)
        provenance["confidence_level"] = confidence_assessment.confidence_level.value
        provenance.setdefault("generation_prompt_version", meta.get("generation_prompt_version"))
        provenance.setdefault("generated_at", meta.get("generated_at"))
        provenance.setdefault("requires_human_review", True)

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
            "provenance": provenance,
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
        top_level_selected_evidence_ids,
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

        for value in top_level_selected_evidence_ids or []:
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

        for item in selected_achievements or []:
            normalized = str(item.get("id") or item.get("title") or "").strip()
            if normalized:
                ids.append(normalized)

        return ids

    def _extract_selected_achievement_ids(
        self,
        selected_achievement_ids,
        top_level_selected_achievement_ids,
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

        for value in top_level_selected_achievement_ids or []:
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

    @staticmethod
    def _confidence_item_from_selected_achievement(item: dict) -> dict:
        fact_status = str(item.get("fact_status") or "").strip().lower()
        metric_text = str(item.get("metric_text") or "").strip()
        star_summary = {
            "situation": item.get("situation"),
            "task": item.get("task"),
            "action": item.get("action"),
            "result": item.get("result"),
        }
        if fact_status == "confirmed" and metric_text:
            evidence_strength = "strong"
        elif fact_status == "confirmed" and any(
            str(star_summary.get(field) or "").strip()
            for field in ("situation", "task", "action", "result")
        ):
            evidence_strength = "medium"
        elif fact_status == "confirmed":
            evidence_strength = "weak"
        elif fact_status in {"needs_confirmation", "partial", "pending"}:
            evidence_strength = "weak"
        else:
            evidence_strength = "weak"

        return {
            "id": item.get("id"),
            "title": item.get("title"),
            "fact_status": fact_status,
            "evidence_strength": evidence_strength,
            "star_summary": star_summary,
        }
