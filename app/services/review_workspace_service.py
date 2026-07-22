# app/services/review_workspace_service.py

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.domain.readiness_models import ReadinessScore
from app.domain.review_models import (
    ClaimResolution,
    DocumentWarning,
    ReviewWorkspace,
)
from app.repositories.candidate_achievement_repository import CandidateAchievementRepository
from app.repositories.document_version_repository import DocumentVersionRepository
from app.repositories.pipeline_repository import SQLAlchemyAsyncPipelineRepository
from app.repositories.review_workflow_repository import ReviewWorkflowRepository
from app.repositories.vacancy_analysis_repository import VacancyAnalysisRepository

logger = logging.getLogger(__name__)


class ReviewWorkspaceService:
    """Service for building unified ReviewWorkspace aggregates."""

    def __init__(
        self,
        document_repo: DocumentVersionRepository | None = None,
        pipeline_repo: SQLAlchemyAsyncPipelineRepository | None = None,
        vacancy_analysis_repo: VacancyAnalysisRepository | None = None,
        review_workflow_repo: ReviewWorkflowRepository | None = None,
        achievement_repo: CandidateAchievementRepository | None = None,
    ):
        self.document_repo = document_repo or DocumentVersionRepository()
        self.pipeline_repo = pipeline_repo or SQLAlchemyAsyncPipelineRepository(None)
        self.vacancy_analysis_repo = vacancy_analysis_repo or VacancyAnalysisRepository()
        self.review_workflow_repo = review_workflow_repo or ReviewWorkflowRepository()
        self.achievement_repo = achievement_repo or CandidateAchievementRepository()

    @staticmethod
    def parse_workspace_id(workspace_id: str) -> tuple[UUID, UUID, UUID | None]:
        parts = workspace_id.split("_")
        if len(parts) < 3 or parts[0] != "ws":
            raise ValueError("Invalid workspace ID format")

        document_id = UUID(parts[1])
        user_id = UUID(parts[2])
        pipeline_execution_id = UUID(parts[3]) if len(parts) > 3 else None
        return document_id, user_id, pipeline_execution_id

    async def build_review_workspace(
        self,
        document_id: UUID,
        user_id: UUID,
        pipeline_execution_id: UUID | None = None,
        session=None,
    ) -> ReviewWorkspace:
        """Build complete ReviewWorkspace from document and related data."""

        # Get document
        document = await self.document_repo.get_document_version(document_id, session=session)
        if not document:
            raise ValueError(f"Document {document_id} not found")

        # Get pipeline execution if provided
        pipeline_execution = None
        if pipeline_execution_id:
            pipeline_execution = await self.pipeline_repo.get_execution(pipeline_execution_id)

        # Get evaluation snapshot
        evaluation_report = None
        if pipeline_execution and pipeline_execution.evaluation_snapshot_id:
            evaluation = await self.vacancy_analysis_repo.get_analysis(
                pipeline_execution.evaluation_snapshot_id, session=session
            )
            if evaluation:
                evaluation_report = evaluation.analysis_data

        # Build workspace
        workspace = ReviewWorkspace(
            workspace_id=f"ws_{document_id}_{user_id}",
            document_id=str(document_id),
            user_id=str(user_id),
            pipeline_execution_id=str(pipeline_execution_id) if pipeline_execution_id else None,
            document=document.content_json if document.content_json else None,
            document_version=document.version,
            evaluation_report=evaluation_report,
        )

        # Extract issues from evaluation report
        if evaluation_report:
            workspace = self._extract_evaluation_issues(workspace, evaluation_report)

        # Extract readiness data
        if pipeline_execution and pipeline_execution.metrics_json:
            workspace = self._extract_readiness_data(workspace, pipeline_execution.metrics_json)

        # Calculate diff from previous version
        workspace = await self._calculate_version_diff(workspace, document_id, session)

        return workspace

    def _extract_evaluation_issues(
        self,
        workspace: ReviewWorkspace,
        evaluation_report: dict[str, Any],
    ) -> ReviewWorkspace:
        """Extract warnings, critical failures, and claims from evaluation report."""

        # Extract critical failures
        critical_failures = evaluation_report.get("critical_failures", [])
        for failure in critical_failures:
            workspace.critical_failures.append(DocumentWarning(
                code=failure.get("code", "unknown"),
                message=failure.get("message", "Critical failure"),
                severity="critical",
                section=failure.get("section"),
                claim_text=failure.get("claim_text"),
            ))

        # Extract warnings
        warnings = evaluation_report.get("warnings", [])
        for warning in warnings:
            workspace.warnings.append(DocumentWarning(
                code=warning.get("code", "unknown"),
                message=warning.get("message", "Warning"),
                severity=warning.get("severity", "warning"),
                section=warning.get("section"),
                claim_text=warning.get("claim_text"),
            ))

        # Extract claims needing confirmation
        unresolved_claims = evaluation_report.get("unresolved_claims", [])
        for claim in unresolved_claims:
            workspace.claims_needing_confirmation.append(ClaimResolution(
                claim_text=claim.get("text", ""),
                fact_status="needs_confirmation",
                resolution_reason=claim.get("reason"),
            ))

        # Extract resolved claims
        resolved_claims = evaluation_report.get("resolved_claims", [])
        for claim in resolved_claims:
            workspace.resolved_claims.append(ClaimResolution(
                claim_text=claim.get("text", ""),
                fact_status=claim.get("status", "confirmed"),
                resolved_at=claim.get("resolved_at"),
                resolution_reason=claim.get("reason"),
            ))

        # Extract coverage gaps
        coverage_gaps = evaluation_report.get("coverage_gaps", [])
        workspace.coverage_gaps = coverage_gaps

        return workspace

    def _extract_readiness_data(
        self,
        workspace: ReviewWorkspace,
        metrics_json: dict[str, Any],
    ) -> ReviewWorkspace:
        """Extract readiness score and recommendation tasks from metrics."""

        # Extract readiness score
        readiness_data = metrics_json.get("readiness_score")
        if readiness_data:
            workspace.readiness_score = ReadinessScore(
                overall_score=readiness_data.get("overall_score", 0.0),
                ats_score=readiness_data.get("ats_score", 0.0),
                evidence_score=readiness_data.get("evidence_score", 0.0),
                interview_score=readiness_data.get("interview_score", 0.0),
                coverage_score=readiness_data.get("coverage_score", 0.0),
                quality_score=readiness_data.get("quality_score", 0.0),
                blocking_issues=readiness_data.get("blocking_issues", []),
                warnings=readiness_data.get("warnings", []),
                recommendations=readiness_data.get("recommendations", []),
                recommendation_tasks=readiness_data.get("recommendation_tasks", []),
            )

            # Extract recommendation tasks
            workspace.recommendation_tasks = readiness_data.get("recommendation_tasks", [])

        return workspace

    async def _calculate_version_diff(
        self,
        workspace: ReviewWorkspace,
        document_id: UUID,
        session=None,
    ) -> ReviewWorkspace:
        """Calculate diff from previous document version."""

        # Get previous version
        previous_version = await self.document_repo.get_previous_version(document_id, session=session)
        if previous_version:
            workspace.previous_version_id = str(previous_version.id)

            # Simple diff calculation (in real implementation, use proper diff library)
            workspace.diff_from_previous = {
                "changes_detected": True,
                "sections_modified": ["experience", "skills"],  # Placeholder
                "content_changes": 15,  # Placeholder
            }

        return workspace

    async def update_workspace_status(
        self,
        workspace_id: str,
        new_status: str,
        reviewer_id: str | None = None,
    ) -> None:
        """Update workspace status and reviewer."""
        logger.info(
            f"Updating workspace {workspace_id} status to {new_status}",
            extra={"workspace_id": workspace_id, "reviewer_id": reviewer_id},
        )
        # In real implementation, persist workspace status
        # For now, this is a placeholder

    async def record_review_action(
        self,
        *,
        session,
        workspace_id: str,
        action_type: str,
        target_type: str | None = None,
        target_id: str | None = None,
        payload: dict[str, Any] | None = None,
        reviewer_id: UUID | None = None,
    ):
        document_id, user_id, pipeline_execution_id = self.parse_workspace_id(workspace_id)
        action_payload = payload or {}
        supported_actions = {
            "approve_claim",
            "reject_claim",
            "edit_section",
            "approve_document",
            "reject_document",
        }
        if action_type not in supported_actions:
            raise ValueError(f"Unsupported review action: {action_type}")

        if target_type == "claim" and target_id and action_type in {"approve_claim", "reject_claim"}:
            fact_status = "confirmed" if action_type == "approve_claim" else "rejected"
            achievement = await self.achievement_repo.get_by_id_for_user(
                session,
                achievement_id=UUID(target_id),
                user_id=user_id,
            )
            if achievement is None:
                raise ValueError("Claim target not found")

            achievement.fact_status = fact_status
            if action_payload.get("evidence_note") is not None:
                achievement.evidence_note = str(action_payload["evidence_note"]).strip() or None
            await session.flush()

        review_session = await self.review_workflow_repo.get_open_session(
            session,
            document_id=document_id,
            user_id=user_id,
        )
        if review_session is None:
            review_session = await self.review_workflow_repo.create_session(
                session,
                session_id=f"review_{workspace_id}_{int(datetime.now(timezone.utc).timestamp())}",
                document_id=document_id,
                user_id=user_id,
                started_at=datetime.now(timezone.utc),
                review_required=True,
                status="review_required",
                pipeline_execution_id=pipeline_execution_id,
                reviewer_id=reviewer_id,
                review_reason=action_payload.get("reason"),
                metadata={"workspace_id": workspace_id},
            )

        if reviewer_id is not None and review_session.reviewer_id is None:
            review_session.reviewer_id = reviewer_id
            await session.flush()

        action = await self.review_workflow_repo.record_action(
            session,
            review_session_id=review_session.id,
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            action_payload=action_payload,
        )

        if action_type in {"approve_document", "reject_document"}:
            outcome_status = "approved" if action_type == "approve_document" else "rejected"
            await self.review_workflow_repo.record_outcome(
                session,
                review_session_id=review_session.id,
                outcome_status=outcome_status,
                approved=action_type == "approve_document",
                outcome_payload={
                    "workspace_id": workspace_id,
                    "action_type": action_type,
                    "target_type": target_type,
                    "target_id": target_id,
                    **action_payload,
                },
            )
            await self.review_workflow_repo.complete_session(
                session,
                review_session_id=review_session.id,
                completed_at=datetime.now(timezone.utc),
                final_status=outcome_status,
                reviewer_id=reviewer_id,
            )
            return action, "completed"

        return action, "recorded"
