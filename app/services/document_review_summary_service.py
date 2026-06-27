# app\services\document_review_summary_service.py

from __future__ import annotations

from app.domain.evidence_confidence import aggregate_evidence_confidence
from app.services.document_quality_service import DocumentQualityService
from app.services.readiness_gate_service import ReadinessGateService


class DocumentReviewSummaryService:
    def __init__(
        self,
        readiness_gate_service: ReadinessGateService | None = None,
        quality_service: DocumentQualityService | None = None,
    ) -> None:
        self.readiness_gate_service = readiness_gate_service or ReadinessGateService()
        self.quality_service = quality_service or DocumentQualityService()

    def build_summary(self, document) -> dict:
        content = document.content_json or {}
        sections = content.get("sections", {})
        meta = content.get("meta", {})
        provenance = dict(content.get("provenance") or meta.get("provenance") or {})
        readiness = self.readiness_gate_service.evaluate_document_readiness(document)
        raw_document_kind = getattr(document, "document_kind", "") or ""
        document_kind = str(getattr(raw_document_kind, "value", raw_document_kind))
        quality = self._build_quality(document_kind=document_kind, document=document)

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
        selected_evidence = self._build_selected_evidence(
            selected_achievements=selected_achievements,
            selected_evidence_ids=selected_evidence_ids,
            evidence_selection_reason=evidence_selection_reason,
        )
        matched_keywords = self._extract_matched_keywords(sections)

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
            "selected_evidence": selected_evidence,
            "unused_evidence": [],
            "matched_keywords": matched_keywords,
            "missing_keywords": sections.get("missing_keywords", []),
            "selection_rationale": sections.get("selection_rationale", []),
            "provenance": provenance,
            "quality": quality,
            "readiness": {
                "ready": readiness.ready,
                "blockers": readiness.blockers,
                "warnings": readiness.warnings,
                "score": readiness.score,
            },
        }

    def _build_quality(self, *, document_kind: str, document) -> dict:
        document_kind = str(document_kind or "").strip().lower()
        content_json = document.content_json or {}
        rendered_text = getattr(document, "rendered_text", None)

        if document_kind == "resume":
            return self.quality_service.evaluate_resume(
                content_json=content_json,
                rendered_text=rendered_text,
            ).as_dict()

        if document_kind == "cover_letter":
            return self.quality_service.evaluate_cover_letter(
                content_json=content_json,
                rendered_text=rendered_text,
            ).as_dict()

        return {}

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

    def _build_selected_evidence(
        self,
        *,
        selected_achievements: list[dict],
        selected_evidence_ids: list[str],
        evidence_selection_reason: list[dict],
    ) -> list[dict]:
        achievements = [
            item
            for item in selected_achievements or []
            if isinstance(item, dict)
        ]
        evidence_by_id = {
            str(item.get("id") or "").strip(): item
            for item in achievements
            if str(item.get("id") or "").strip()
        }

        result: list[dict] = []
        index_by_id: dict[str, int] = {}
        index_by_title: dict[str, int] = {}

        def append_item(
            *,
            evidence_id: str | None,
            title: str | None,
            reason: str | None,
            fact_status: str | None,
            source_type: str = "achievement",
            metric_text: str | None = None,
        ) -> None:
            normalized_id = str(evidence_id or "").strip()
            normalized_title = str(title or "").strip()
            title_key = normalized_title.casefold()

            if not normalized_id and not normalized_title:
                return

            existing_index = (
                index_by_id.get(normalized_id)
                if normalized_id
                else None
            )
            if existing_index is None and title_key:
                existing_index = index_by_title.get(title_key)

            item = {
                "id": normalized_id or normalized_title,
                "title": normalized_title or normalized_id,
                "source_type": source_type,
                "reason": reason,
                "fact_status": fact_status,
                "metric_text": metric_text,
            }

            if existing_index is not None:
                existing = result[existing_index]
                for key, value in item.items():
                    if value and (
                        not existing.get(key)
                        or key == "title"
                        and str(existing.get(key) or "").strip() == normalized_id
                    ):
                        existing[key] = value
                if title_key:
                    index_by_title[title_key] = existing_index
                return

            result.append(item)
            index = len(result) - 1
            if normalized_id:
                index_by_id[normalized_id] = index
            if title_key:
                index_by_title[title_key] = index

        for evidence_id in selected_evidence_ids or []:
            normalized_id = str(evidence_id or "").strip()
            if not normalized_id:
                continue
            achievement = evidence_by_id.get(normalized_id, {})
            append_item(
                evidence_id=normalized_id,
                title=achievement.get("title"),
                reason=achievement.get("reason"),
                fact_status=achievement.get("fact_status"),
                metric_text=achievement.get("metric_text"),
            )

        for reason_item in evidence_selection_reason or []:
            if not isinstance(reason_item, dict):
                continue

            evidence_id = str(reason_item.get("evidence_id") or "").strip()
            achievement_id = str(reason_item.get("achievement_id") or "").strip()
            title = str(reason_item.get("title") or reason_item.get("item") or "").strip()
            achievement = (
                evidence_by_id.get(evidence_id)
                or evidence_by_id.get(achievement_id)
                or {}
            )

            append_item(
                evidence_id=evidence_id or achievement_id or title,
                title=achievement.get("title") or title,
                reason=reason_item.get("reason") or achievement.get("reason"),
                fact_status=reason_item.get("fact_status") or achievement.get("fact_status"),
                source_type=reason_item.get("source_type") or "achievement",
                metric_text=achievement.get("metric_text"),
            )

        for achievement in achievements:
            append_item(
                evidence_id=str(achievement.get("id") or "").strip(),
                title=str(achievement.get("title") or "").strip(),
                reason=achievement.get("reason"),
                fact_status=achievement.get("fact_status"),
                metric_text=achievement.get("metric_text"),
            )

        return result

    def _extract_matched_keywords(self, sections: dict) -> list[str]:
        matched = self._dedupe_strings(sections.get("matched_keywords") or [])
        if matched:
            return matched

        return self._dedupe_strings(sections.get("skills") or [])

    @staticmethod
    def _dedupe_strings(values) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()

        for value in values or []:
            normalized = str(value or "").strip()
            key = normalized.casefold()
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(normalized)

        return result

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
