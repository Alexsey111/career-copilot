# app\services\document_review_service.py

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.document_version_repository import DocumentVersionRepository
from app.services.document_activation_service import (
    DocumentActivationService,
)
from app.domain.review_models import (
    ReviewStatus,
    ReviewerAction,
    is_valid_transition,
    get_allowed_transitions,
)
from app.domain.trace_models import DocumentEvaluationReport


ALLOWED_REVIEW_STATUSES = {"draft", "review_required", "reviewed", "approved", "archived"}


class DocumentReviewService:
    def __init__(
        self,
        document_version_repository: DocumentVersionRepository | None = None,
        document_activation_service: DocumentActivationService | None = None,
    ) -> None:
        self.document_version_repository = (
            document_version_repository
            or DocumentVersionRepository()
        )

        self.document_activation_service = (
            document_activation_service
            or DocumentActivationService(
                document_version_repository=self.document_version_repository,
            )
        )

    def evaluate_review_requirement(
        self,
        evaluation_report: DocumentEvaluationReport,
    ) -> tuple[bool, str]:
        """
        Определяет, требуется ли mandatory review на основе eval результатов.
        
        Returns:
            (requires_review, reason)
        """
        if not evaluation_report.is_safe:
            critical_checks = [
                check for check in evaluation_report.checks
                if check.severity == "critical" and not check.passed
            ]
            if critical_checks:
                reasons = [check.message for check in critical_checks[:3]]
                return True, f"Critical failures detected: {'; '.join(reasons)}"

        warning_checks = [
            check for check in evaluation_report.checks
            if check.severity == "warning" and not check.passed
        ]
        if len(warning_checks) >= 3:
            return True, f"Multiple warnings detected: {len(warning_checks)}"

        return False, "No mandatory review required"

    async def review_document(
        self,
        session: AsyncSession,
        *,
        document_id: UUID,
        user_id: UUID,
        review_status: str,
        review_comment: str | None,
        set_active_when_approved: bool,
        evaluation_report: DocumentEvaluationReport | None = None,
    ):
        normalized_status = review_status.strip().lower()
        if normalized_status not in ALLOWED_REVIEW_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"review_status must be one of: {sorted(ALLOWED_REVIEW_STATUSES)}",
            )

        document = await self.document_version_repository.get_by_id(
            session,
            document_id,
            user_id=user_id,
        )
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="document not found",
            )

        # Mandatory review logic: если есть critical failures из eval
        if evaluation_report is not None:
            requires_review, reason = self.evaluate_review_requirement(evaluation_report)
            if requires_review and normalized_status == "approved":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Mandatory review required: {reason}",
                )
            if requires_review:
                normalized_status = "review_required"

        # Валидация перехода статуса
        current_status = document.review_status
        if not is_valid_transition(current_status, normalized_status):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"invalid transition from {current_status} to {normalized_status}. "
                    f"Allowed: {get_allowed_transitions(current_status)}"
                ),
            )

        content_json = dict(document.content_json or {})
        review_section = dict(content_json.get("review", {}))
        review_history = list(review_section.get("history", []))

        review_event = {
            "status": normalized_status,
            "comment": review_comment,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        review_history.append(review_event)

        review_section["latest_status"] = normalized_status
        review_section["latest_comment"] = review_comment
        review_section["history"] = review_history
        content_json["review"] = review_section

        document.review_status = normalized_status
        document.content_json = content_json

        if normalized_status == "approved" and set_active_when_approved:
            await session.commit()

            document = await self.document_activation_service.activate_document(
                session,
                document_id=document.id,
                user_id=user_id,
            )

        elif normalized_status in {"archived"}:
            document.is_active = False

        await session.commit()
        await session.refresh(document)
        return document

    async def submit_review_decisions(
        self,
        session: AsyncSession,
        *,
        document_id: UUID,
        user_id: UUID,
        reviewer_action: ReviewerAction,
        accepted_claims: list[str] | None = None,
        rejected_claims: list[str] | None = None,
        edited_sections: list[str] | None = None,
        reviewer_comment: str | None = None,
    ) -> Any:
        """Завершает review и переводит в reviewed с resolved claims."""
        document = await self.document_version_repository.get_by_id(
            session,
            document_id,
            user_id=user_id,
        )
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="document not found",
            )

        current_status = document.review_status
        if not is_valid_transition(current_status, "reviewed"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"invalid transition from {current_status} to reviewed",
            )

        content = document.content_json or {}
        sections = content.get("sections", {})

        claims_needing_confirmation = sections.get("claims_needing_confirmation", [])
        resolved_claims = sections.get("resolved_claims", [])

        now = datetime.now(timezone.utc).isoformat()

        for claim in claims_needing_confirmation:
            claim_text = claim.get("text", "")
            if claim_text in (accepted_claims or []):
                resolved_claims.append({
                    "claim_text": claim_text,
                    "original_status": claim.get("fact_status", "needs_confirmation"),
                    "final_status": "confirmed",
                    "resolved_at": now,
                    "resolution_reason": "accepted by reviewer",
                })
            elif claim_text in (rejected_claims or []):
                resolved_claims.append({
                    "claim_text": claim_text,
                    "original_status": claim.get("fact_status", "needs_confirmation"),
                    "final_status": "rejected",
                    "resolved_at": now,
                    "resolution_reason": "rejected by reviewer",
                })

        sections["claims_needing_confirmation"] = []
        sections["resolved_claims"] = resolved_claims

        content["meta"] = content.get("meta", {})
        content["meta"]["review_action"] = reviewer_action
        content["meta"]["reviewed_at"] = now
        if reviewer_comment:
            content["meta"]["reviewer_comment"] = reviewer_comment

        document.review_status = "reviewed"
        document.content_json = content
        await session.commit()
        await session.refresh(document)
        return document

    def get_allowed_transitions(
        self,
        current_status: ReviewStatus,
    ) -> set[ReviewStatus]:
        """Возвращает допустимые переходы из текущего статуса."""
        return get_allowed_transitions(current_status)
