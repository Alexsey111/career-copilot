# app/api/routes/review_workspace_routes.py

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.review_workspace import (
    ReviewActionRequest,
    ReviewActionResponse,
    ReviewWorkspaceResponse,
    ReviewWorkspaceSummary,
    ReviewWorkspaceUpdateRequest,
)
from app.services.review_workspace_service import ReviewWorkspaceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/review/workspaces", tags=["Review Workspaces"])


def get_review_workspace_service() -> ReviewWorkspaceService:
    """Dependency injection for review workspace service."""
    from app.repositories.document_version_repository import DocumentVersionRepository
    from app.repositories.pipeline_repository import SQLAlchemyAsyncPipelineRepository
    from app.repositories.review_workflow_repository import ReviewWorkflowRepository
    from app.repositories.vacancy_analysis_repository import VacancyAnalysisRepository

    return ReviewWorkspaceService(
        document_repo=DocumentVersionRepository(),
        pipeline_repo=SQLAlchemyAsyncPipelineRepository(None),
        vacancy_analysis_repo=VacancyAnalysisRepository(),
        review_workflow_repo=ReviewWorkflowRepository(),
    )


@router.get("/{workspace_id}", response_model=ReviewWorkspaceResponse)
async def get_review_workspace(
    workspace_id: str,
    service: ReviewWorkspaceService = Depends(get_review_workspace_service),
    db: AsyncSession = Depends(get_db_session),
):
    """Get complete review workspace by ID."""
    try:
        document_id, user_id, pipeline_execution_id = service.parse_workspace_id(workspace_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid workspace ID format",
        )

    try:
        workspace = await service.build_review_workspace(
            document_id=document_id,
            user_id=user_id,
            pipeline_execution_id=pipeline_execution_id,
            session=db,
        )

        # Convert domain model to response
        response = ReviewWorkspaceResponse(
            workspace_id=workspace.workspace_id,
            document_id=workspace.document_id,
            user_id=workspace.user_id,
            pipeline_execution_id=workspace.pipeline_execution_id,
            document=workspace.document,
            document_version=workspace.document_version,
            evaluation_report=workspace.evaluation_report,
            coverage_gaps=workspace.coverage_gaps,
            critical_failures=workspace.critical_failures,
            warnings=workspace.warnings,
            claims_needing_confirmation=workspace.claims_needing_confirmation,
            resolved_claims=workspace.resolved_claims,
            recommendation_tasks=workspace.recommendation_tasks,
            readiness_score=workspace.readiness_score,
            diff_from_previous=workspace.diff_from_previous,
            previous_version_id=workspace.previous_version_id,
            status=workspace.status,
            created_at=workspace.created_at,
            updated_at=workspace.updated_at,
            reviewer_id=workspace.reviewer_id,
            review_decision=workspace.review_decision,
            has_critical_issues=workspace.has_critical_issues,
            review_priority=workspace.review_priority,
            completion_percentage=workspace.completion_percentage,
            actionable_items_count=workspace.actionable_items_count,
        )

        return response

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to build review workspace: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to build review workspace: {str(e)}",
        )


@router.get("/user/{user_id}", response_model=list[ReviewWorkspaceSummary])
async def get_user_review_workspaces(
    user_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: Optional[str] = None,
    service: ReviewWorkspaceService = Depends(get_review_workspace_service),
    db: AsyncSession = Depends(get_db_session),
):
    """Get review workspaces for a user."""
    # Placeholder implementation - in real system, query actual workspaces
    # For now, return empty list
    return []


@router.patch("/{workspace_id}", response_model=ReviewWorkspaceResponse)
async def update_review_workspace(
    workspace_id: str,
    update_data: ReviewWorkspaceUpdateRequest,
    service: ReviewWorkspaceService = Depends(get_review_workspace_service),
    db: AsyncSession = Depends(get_db_session),
):
    """Update review workspace status and decisions."""
    try:
        # Update workspace status
        if update_data.status:
            await service.update_workspace_status(
                workspace_id=workspace_id,
                new_status=update_data.status,
                reviewer_id=update_data.reviewer_id,
            )

        # Get updated workspace
        return await get_review_workspace(workspace_id, service, db)

    except Exception as e:
        logger.error(f"Failed to update review workspace: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update review workspace: {str(e)}",
        )


@router.post("/{workspace_id}/actions", response_model=ReviewActionResponse)
async def record_review_action(
    workspace_id: str,
    action: ReviewActionRequest,
    service: ReviewWorkspaceService = Depends(get_review_workspace_service),
    db: AsyncSession = Depends(get_db_session),
):
    """Persist a human review action for audit trail and workflow completion."""
    try:
        action_record, action_status = await service.record_review_action(
            session=db,
            workspace_id=workspace_id,
            action_type=action.action_type,
            target_type=action.target_type,
            target_id=action.target_id,
            payload=action.payload,
            reviewer_id=action.reviewer_id,
        )
        await db.commit()
        return ReviewActionResponse(
            action_id=action_record.id,
            workspace_id=workspace_id,
            action_type=action_record.action_type,
            status=action_status,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = (
            status.HTTP_400_BAD_REQUEST
            if detail == "Invalid workspace ID format" or detail.startswith("Unsupported review action:")
            else status.HTTP_404_NOT_FOUND
        )
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except Exception as e:
        logger.error(f"Failed to record review action: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record review action: {str(e)}",
        )


@router.post("/from-pipeline/{pipeline_execution_id}", response_model=ReviewWorkspaceResponse)
async def create_review_workspace_from_pipeline(
    pipeline_execution_id: UUID,
    service: ReviewWorkspaceService = Depends(get_review_workspace_service),
    db: AsyncSession = Depends(get_db_session),
):
    """Create review workspace from pipeline execution results."""
    try:
        # Get pipeline execution to extract document and user IDs
        pipeline_execution = await service.pipeline_repo.get_execution(pipeline_execution_id)
        if not pipeline_execution:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pipeline execution {pipeline_execution_id} not found",
            )

        if not pipeline_execution.resume_document_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pipeline execution has no resume document",
            )

        # Build workspace
        workspace = await service.build_review_workspace(
            document_id=pipeline_execution.resume_document_id,
            user_id=pipeline_execution.user_id,
            pipeline_execution_id=pipeline_execution_id,
            session=db,
        )

        # Convert to response
        response = ReviewWorkspaceResponse(
            workspace_id=workspace.workspace_id,
            document_id=workspace.document_id,
            user_id=workspace.user_id,
            pipeline_execution_id=workspace.pipeline_execution_id,
            document=workspace.document,
            document_version=workspace.document_version,
            evaluation_report=workspace.evaluation_report,
            coverage_gaps=workspace.coverage_gaps,
            critical_failures=workspace.critical_failures,
            warnings=workspace.warnings,
            claims_needing_confirmation=workspace.claims_needing_confirmation,
            resolved_claims=workspace.resolved_claims,
            recommendation_tasks=workspace.recommendation_tasks,
            readiness_score=workspace.readiness_score,
            diff_from_previous=workspace.diff_from_previous,
            previous_version_id=workspace.previous_version_id,
            status=workspace.status,
            created_at=workspace.created_at,
            updated_at=workspace.updated_at,
            reviewer_id=workspace.reviewer_id,
            review_decision=workspace.review_decision,
            has_critical_issues=workspace.has_critical_issues,
            review_priority=workspace.review_priority,
            completion_percentage=workspace.completion_percentage,
            actionable_items_count=workspace.actionable_items_count,
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create review workspace from pipeline: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create review workspace: {str(e)}",
        )
