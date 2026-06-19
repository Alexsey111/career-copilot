# app/services/review_summary_service.py

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.document_version_repository import DocumentVersionRepository
from app.repositories.interview_prep_session_repository import (
    InterviewPrepSessionRepository,
)
from app.domain.evidence_confidence import aggregate_evidence_confidence
from app.services.document_review_summary_service import DocumentReviewSummaryService


class ReviewSummaryService:
    def __init__(
        self,
        *,
        document_repository: DocumentVersionRepository | None = None,
        interview_prep_repository: InterviewPrepSessionRepository | None = None,
        document_summary_service: DocumentReviewSummaryService | None = None,
    ) -> None:
        self.document_repository = document_repository or DocumentVersionRepository()
        self.interview_prep_repository = (
            interview_prep_repository or InterviewPrepSessionRepository()
        )
        self.document_summary_service = (
            document_summary_service or DocumentReviewSummaryService()
        )

    async def build_summary(
        self,
        session: AsyncSession,
        *,
        entity_type: Literal["document", "interview_prep"],
        entity_id: UUID,
        user_id: UUID,
    ) -> dict[str, Any]:
        if entity_type == "document":
            document = await self.document_repository.get_by_id(
                session,
                entity_id,
                user_id=user_id,
            )
            if document is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="document not found",
                )
            return self._build_document_summary(document=document, entity_id=entity_id)

        if entity_type == "interview_prep":
            prep_session = await self.interview_prep_repository.get_by_id(
                session,
                entity_id,
                user_id=user_id,
            )
            if prep_session is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="interview prep session not found",
                )
            return self._build_interview_prep_summary(
                prep_session=prep_session,
                entity_id=entity_id,
            )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="entity_type must be one of: document, interview_prep",
        )

    def _build_document_summary(self, *, document, entity_id: UUID) -> dict[str, Any]:
        summary = self.document_summary_service.build_summary(document)
        quality = dict(summary.get("quality") or {})
        readiness = summary["readiness"]
        provenance_summary = self._normalize_provenance_confidence(
            dict(summary.get("provenance") or {}),
            evidence_items=summary.get("selected_achievements") or [],
        )
        claims_requiring_confirmation = list(summary.get("claims_needing_confirmation") or [])
        if claims_requiring_confirmation:
            provenance_summary["confidence"] = min(
                float(provenance_summary.get("confidence") or 1.0),
                0.49,
            )
            provenance_summary["confidence_level"] = "needs_review"
            provenance_summary["requires_human_review"] = True
        warnings = self._merge_unique_strings(
            list(readiness.get("warnings") or []),
            [
                str(item.get("message") or "").strip()
                for item in (summary.get("warnings") or [])
                if isinstance(item, dict) and str(item.get("message") or "").strip()
            ],
        )
        gap_risk_items = self._document_gap_risk_items(summary)
        selected_evidence = self._document_selected_evidence(summary)

        return self._to_payload(
            entity_type="document",
            entity_id=entity_id,
            ready=bool(readiness["ready"]),
            blockers=list(readiness.get("blockers") or []),
            warnings=warnings,
            claims_requiring_confirmation=claims_requiring_confirmation,
            gap_risk_items=gap_risk_items,
            selected_evidence=selected_evidence,
            provenance_summary=provenance_summary,
            quality=quality,
            recommended_actions=self._recommended_actions(
                entity_type="document",
                ready=bool(readiness["ready"]),
                blockers=list(readiness.get("blockers") or []),
                warnings=warnings,
                claims_requiring_confirmation=claims_requiring_confirmation,
                gap_risk_items=gap_risk_items,
                provenance_summary=provenance_summary,
                selected_evidence=selected_evidence,
            ),
        )

    def _build_interview_prep_summary(self, *, prep_session, entity_id: UUID) -> dict[str, Any]:
        readiness = prep_session.readiness_json or {}
        questions = list(prep_session.question_set_json or [])
        evidence_links = list(prep_session.evidence_links_json or [])
        weak_areas = list(prep_session.weak_areas_json or [])
        provenance_summary = self._normalize_provenance_confidence(
            dict(readiness.get("provenance") or {}),
            evidence_items=questions,
            gap_risk=any(str(question.get("category") or "").lower() == "gap-risk" for question in questions),
        )
        warnings = self._merge_unique_strings(
            list(readiness.get("warnings") or []),
            [
                str(item.get("message") or "").strip()
                for item in weak_areas
                if isinstance(item, dict)
                and str(item.get("severity") or "").lower() == "warning"
                and str(item.get("message") or "").strip()
            ],
        )
        gap_risk_items = self._interview_gap_risk_items(
            questions=questions,
            weak_areas=weak_areas,
        )
        selected_evidence = self._interview_selected_evidence(
            questions=questions,
            evidence_links=evidence_links,
        )

        return self._to_payload(
            entity_type="interview_prep",
            entity_id=entity_id,
            ready=bool(readiness.get("ready")),
            blockers=list(readiness.get("blockers") or []),
            warnings=warnings,
            claims_requiring_confirmation=[],
            gap_risk_items=gap_risk_items,
            selected_evidence=selected_evidence,
            provenance_summary=provenance_summary,
            quality={},
            recommended_actions=self._recommended_actions(
                entity_type="interview_prep",
                ready=bool(readiness.get("ready")),
                blockers=list(readiness.get("blockers") or []),
                warnings=warnings,
                claims_requiring_confirmation=[],
                gap_risk_items=gap_risk_items,
                provenance_summary=provenance_summary,
                selected_evidence=selected_evidence,
            ),
        )

    def _to_payload(
        self,
        *,
        entity_type: Literal["document", "interview_prep"],
        entity_id: UUID,
        ready: bool,
        blockers: list[str],
        warnings: list[str],
        claims_requiring_confirmation: list[dict[str, Any]],
        gap_risk_items: list[dict[str, Any]],
        selected_evidence: list[dict[str, Any]],
        provenance_summary: dict[str, Any],
        quality: dict[str, Any],
        recommended_actions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "ready": ready,
            "requires_human_review": True,
            "risk_level": self._risk_level(
                ready=ready,
                blockers=blockers,
                warnings=warnings,
                claims_requiring_confirmation=claims_requiring_confirmation,
                gap_risk_items=gap_risk_items,
            ),
            "blockers": blockers,
            "warnings": warnings,
            "claims_requiring_confirmation": claims_requiring_confirmation,
            "gap_risk_items": gap_risk_items,
            "selected_evidence": selected_evidence,
            "provenance_summary": provenance_summary,
            "quality": quality,
            "recommended_actions": recommended_actions,
        }

    def _risk_level(
        self,
        *,
        ready: bool,
        blockers: list[str],
        warnings: list[str],
        claims_requiring_confirmation: list[dict[str, Any]],
        gap_risk_items: list[dict[str, Any]],
    ) -> Literal["low", "medium", "high"]:
        if blockers:
            return "high"
        if claims_requiring_confirmation:
            return "high"
        if not ready:
            return "medium"
        if warnings or gap_risk_items:
            return "medium"
        return "low"

    def _recommended_actions(
        self,
        *,
        entity_type: Literal["document", "interview_prep"],
        ready: bool,
        blockers: list[str],
        warnings: list[str],
        claims_requiring_confirmation: list[dict[str, Any]],
        gap_risk_items: list[dict[str, Any]],
        provenance_summary: dict[str, Any],
        selected_evidence: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []

        actions.extend(
            self._actions_from_blockers(
                entity_type=entity_type,
                blockers=blockers,
            )
        )
        actions.extend(
            self._actions_from_claims(
                claims_requiring_confirmation=claims_requiring_confirmation,
            )
        )
        actions.extend(
            self._actions_from_gap_risk_items(
                entity_type=entity_type,
                gap_risk_items=gap_risk_items,
            )
        )
        actions.extend(
            self._actions_from_confidence(
                entity_type=entity_type,
                entity_id=provenance_summary.get("application_id")
                or provenance_summary.get("analysis_id")
                or provenance_summary.get("document_id")
                or provenance_summary.get("vacancy_id"),
                provenance_summary=provenance_summary,
            )
        )
        actions.extend(
            self._actions_from_missing_evidence(
                entity_type=entity_type,
                entity_id=provenance_summary.get("application_id")
                or provenance_summary.get("analysis_id")
                or provenance_summary.get("document_id")
                or provenance_summary.get("vacancy_id"),
                selected_evidence=selected_evidence,
            )
        )
        actions.extend(
            self._actions_from_warnings(
                entity_type=entity_type,
                warnings=warnings,
            )
        )

        if ready and not actions:
            actions.append(
                {
                    "code": f"{entity_type}_review_and_publish",
                    "label": "Review once more before publishing",
                    "severity": "info",
                    "target_type": entity_type,
                    "target_id": None,
                    "reason": "Draft is ready but still requires final human review",
                }
            )

        if provenance_summary.get("requires_human_review") is True and not actions:
            actions.append(
                {
                    "code": f"{entity_type}_human_review",
                    "label": "Complete human review",
                    "severity": "info",
                    "target_type": entity_type,
                    "target_id": None,
                    "reason": "Human review is still required before final use",
                }
            )

        return self._dedupe_actions(actions)

    def _actions_from_blockers(
        self,
        *,
        entity_type: Literal["document", "interview_prep"],
        blockers: list[str],
    ) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        for index, blocker in enumerate(blockers):
            normalized = str(blocker or "").strip()
            if not normalized:
                continue
            actions.append(
                {
                    "code": "resolve_blocker",
                    "label": "Resolve blocker",
                    "severity": "blocker",
                    "target_type": entity_type,
                    "target_id": f"{entity_type}:{index}",
                    "reason": normalized,
                }
            )
        return actions

    def _actions_from_claims(
        self,
        *,
        claims_requiring_confirmation: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        for claim in claims_requiring_confirmation:
            if not isinstance(claim, dict):
                continue
            target_id = str(claim.get("claim_text") or claim.get("text") or "").strip()
            if not target_id:
                continue
            actions.append(
                {
                    "code": "confirm_claim",
                    "label": "Confirm or edit unsupported claim",
                    "severity": "blocker",
                    "target_type": "document_claim",
                    "target_id": target_id,
                    "reason": "Document contains claims requiring confirmation",
                }
            )
        return actions

    def _actions_from_gap_risk_items(
        self,
        *,
        entity_type: Literal["document", "interview_prep"],
        gap_risk_items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        for item in gap_risk_items:
            if not isinstance(item, dict):
                continue
            if entity_type == "document":
                keyword = str(item.get("keyword") or "").strip()
                if not keyword:
                    continue
                actions.append(
                    {
                        "code": "attach_missing_evidence",
                        "label": "Attach supporting evidence",
                        "severity": "warning",
                        "target_type": "document_gap",
                        "target_id": keyword,
                        "reason": item.get("message") or "Document is missing vacancy coverage",
                    }
                )
                continue

            question_id = str(item.get("question_id") or "").strip()
            if not question_id:
                continue
            actions.append(
                {
                    "code": "prepare_gap_response",
                    "label": "Prepare a careful gap-risk response",
                    "severity": "warning",
                    "target_type": "interview_question",
                    "target_id": question_id,
                    "reason": item.get("message") or "Gap-risk question needs careful answer",
                }
            )
        return actions

    def _actions_from_confidence(
        self,
        *,
        entity_type: Literal["document", "interview_prep"],
        entity_id: Any,
        provenance_summary: dict[str, Any],
    ) -> list[dict[str, Any]]:
        confidence_level = str(provenance_summary.get("confidence_level") or "").strip().lower()
        confidence = provenance_summary.get("confidence")
        if confidence is None:
            return []
        if confidence_level not in {"low", "needs_review"} and not (
            isinstance(confidence, (int, float)) and float(confidence) < 0.6
        ):
            return []

        return [
            {
                "code": "review_low_confidence",
                "label": "Review low-confidence content",
                "severity": "warning",
                "target_type": entity_type,
                "target_id": str(entity_id) if entity_id is not None else None,
                "reason": "Evidence confidence is low or requires review",
            }
        ]

    def _actions_from_missing_evidence(
        self,
        *,
        entity_type: Literal["document", "interview_prep"],
        entity_id: Any,
        selected_evidence: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if selected_evidence:
            return []

        return [
            {
                "code": "attach_missing_evidence",
                "label": "Attach or review supporting evidence",
                "severity": "warning",
                "target_type": entity_type,
                "target_id": str(entity_id) if entity_id is not None else None,
                "reason": "No selected evidence was found for this draft",
            }
        ]

    def _actions_from_warnings(
        self,
        *,
        entity_type: Literal["document", "interview_prep"],
        warnings: list[str],
    ) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        for index, warning in enumerate(warnings):
            normalized = str(warning or "").strip()
            if not normalized:
                continue
            actions.append(
                {
                    "code": "review_warning",
                    "label": "Review warning",
                    "severity": "warning",
                    "target_type": entity_type,
                    "target_id": f"{entity_type}:warning:{index}",
                    "reason": normalized,
                }
            )
        return actions

    @staticmethod
    def _dedupe_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str | None, str | None]] = set()

        for action in actions:
            key = (
                str(action.get("code") or ""),
                str(action.get("target_type") or ""),
                str(action.get("target_id") or "") or None,
                str(action.get("reason") or "") or None,
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(action)

        return deduped

    def _document_selected_evidence(self, summary: dict[str, Any]) -> list[dict[str, Any]]:
        selected_achievements = list(summary.get("selected_achievements") or [])
        selected_evidence_ids = list(summary.get("selected_evidence_ids") or [])
        evidence_by_id = {
            str(item.get("id") or ""): item
            for item in selected_achievements
            if isinstance(item, dict) and str(item.get("id") or "").strip()
        }

        evidence_items: list[dict[str, Any]] = []
        for evidence_id in selected_evidence_ids:
            normalized_id = str(evidence_id or "").strip()
            if not normalized_id:
                continue
            achievement = evidence_by_id.get(normalized_id, {})
            evidence_items.append(
                {
                    "id": normalized_id,
                    "title": achievement.get("title"),
                    "source_type": "achievement",
                    "reason": achievement.get("reason"),
                    "fact_status": achievement.get("fact_status"),
                    "metric_text": achievement.get("metric_text"),
                }
            )
        return evidence_items

    def _interview_selected_evidence(
        self,
        *,
        questions: list[dict[str, Any]],
        evidence_links: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        question_by_id = {
            str(item.get("question_id") or ""): item
            for item in questions
            if isinstance(item, dict) and str(item.get("question_id") or "").strip()
        }

        selected: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for link in evidence_links:
            if not isinstance(link, dict):
                continue
            question_id = str(link.get("question_id") or "").strip()
            achievement_id = str(link.get("achievement_id") or "").strip()
            if not question_id or not achievement_id:
                continue
            dedupe_key = (question_id, achievement_id)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            question = question_by_id.get(question_id, {})
            selected.append(
                {
                    "id": achievement_id,
                    "question_id": question_id,
                    "title": link.get("achievement_title"),
                    "source_type": question.get("source_type") or "achievement",
                    "source_requirement": question.get("source_requirement"),
                    "reason": link.get("reason"),
                    "score": link.get("score"),
                    "fact_status": question.get("fact_status"),
                }
            )

        return selected

    def _document_gap_risk_items(self, summary: dict[str, Any]) -> list[dict[str, Any]]:
        missing_keywords = list(summary.get("missing_keywords") or [])
        gap_risk_items: list[dict[str, Any]] = []

        for keyword in missing_keywords:
            normalized = str(keyword or "").strip()
            if not normalized:
                continue
            gap_risk_items.append(
                {
                    "code": f"missing_keyword_{normalized.lower().replace(' ', '_')}",
                    "message": f"Missing vacancy keyword: {normalized}",
                    "severity": "warning",
                    "source_type": "vacancy_gap",
                    "keyword": normalized,
                }
            )

        return gap_risk_items

    @staticmethod
    def _normalize_provenance_confidence(
        provenance_summary: dict[str, Any],
        *,
        evidence_items: list[dict[str, Any]],
        gap_risk: bool = False,
    ) -> dict[str, Any]:
        if provenance_summary.get("confidence_level") and provenance_summary.get("confidence") is not None:
            return provenance_summary

        assessment = aggregate_evidence_confidence(
            [
                item
                for item in evidence_items
                if isinstance(item, dict)
            ],
            gap_risk=gap_risk,
        )
        provenance_summary.setdefault("confidence", assessment.confidence)
        provenance_summary.setdefault("confidence_level", assessment.confidence_level.value)
        provenance_summary.setdefault("requires_human_review", assessment.requires_human_review)
        return provenance_summary

    @staticmethod
    def _merge_unique_strings(*groups: list[str]) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()

        for group in groups:
            for value in group:
                normalized = str(value or "").strip()
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                merged.append(normalized)

        return merged

    def _interview_gap_risk_items(
        self,
        *,
        questions: list[dict[str, Any]],
        weak_areas: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        gap_risk_items: list[dict[str, Any]] = []

        for item in weak_areas:
            if not isinstance(item, dict):
                continue
            if str(item.get("severity") or "").lower() not in {"blocker", "warning"}:
                continue
            gap_risk_items.append(
                {
                    "code": item.get("code"),
                    "message": item.get("message"),
                    "severity": item.get("severity"),
                    "source_type": "weak_area",
                    "competency_key": item.get("competency_key"),
                }
            )

        for question in questions:
            if not isinstance(question, dict):
                continue
            if question.get("category") != "gap-risk":
                continue
            gap_risk_items.append(
                {
                    "code": f"question_{question.get('question_id')}",
                    "question_id": question.get("question_id"),
                    "message": question.get("prompt"),
                    "severity": "warning",
                    "source_type": "gap_question",
                    "competency_key": question.get("competency_key"),
                    "requires_careful_answer": question.get("requires_careful_answer", True),
                }
            )

        return gap_risk_items
