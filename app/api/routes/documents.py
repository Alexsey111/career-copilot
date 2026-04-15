# app\api\routes\documents.py

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_dev_user
from app.db.session import get_db_session
from app.models import User
from app.repositories.document_version_repository import DocumentVersionRepository
from app.schemas.document import (
    CoverLetterGenerateRequest,
    CoverLetterGenerateResponse,
    DocumentReviewRequest,
    DocumentReviewResponse,
    DocumentVersionRead,
    ResumeGenerateRequest,
    ResumeGenerateResponse,
)
from app.services.cover_letter_generation_service import CoverLetterGenerationService
from app.services.document_review_service import DocumentReviewService
from app.services.resume_generation_service import ResumeGenerationService


router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/resumes/generate", response_model=ResumeGenerateResponse)
async def generate_resume(
    payload: ResumeGenerateRequest,
    current_user: User = Depends(get_current_dev_user),
    session: AsyncSession = Depends(get_db_session),
) -> ResumeGenerateResponse:
    service = ResumeGenerationService()
    document = await service.generate_resume(
        session,
        vacancy_id=payload.vacancy_id,
        user_id=current_user.id,
    )

    preview = (document.rendered_text or "")[:1200]

    return ResumeGenerateResponse(
        document_id=document.id,
        vacancy_id=document.vacancy_id,
        review_status=document.review_status,
        version_label=document.version_label,
        created_at=document.created_at,
        rendered_text_preview=preview,
    )


@router.post("/letters/generate", response_model=CoverLetterGenerateResponse)
async def generate_cover_letter(
    payload: CoverLetterGenerateRequest,
    current_user: User = Depends(get_current_dev_user),
    session: AsyncSession = Depends(get_db_session),
) -> CoverLetterGenerateResponse:
    service = CoverLetterGenerationService()
    document = await service.generate_cover_letter(
        session,
        vacancy_id=payload.vacancy_id,
        user_id=current_user.id,
    )

    preview = (document.rendered_text or "")[:1200]

    return CoverLetterGenerateResponse(
        document_id=document.id,
        vacancy_id=document.vacancy_id,
        review_status=document.review_status,
        version_label=document.version_label,
        created_at=document.created_at,
        rendered_text_preview=preview,
    )


@router.get("/{document_id}", response_model=DocumentVersionRead)
async def get_document(
    document_id: UUID,
    current_user: User = Depends(get_current_dev_user),
    session: AsyncSession = Depends(get_db_session),
) -> DocumentVersionRead:
    repo = DocumentVersionRepository()
    document = await repo.get_by_id(session, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="document not found",
        )
    if document.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="document not found",
        )

    return DocumentVersionRead(
        id=document.id,
        vacancy_id=document.vacancy_id,
        document_kind=document.document_kind,
        version_label=document.version_label,
        review_status=document.review_status,
        is_active=document.is_active,
        rendered_text=document.rendered_text,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@router.patch("/{document_id}/review", response_model=DocumentReviewResponse)
async def review_document(
    document_id: UUID,
    payload: DocumentReviewRequest,
    current_user: User = Depends(get_current_dev_user),
    session: AsyncSession = Depends(get_db_session),
) -> DocumentReviewResponse:
    service = DocumentReviewService()
    document = await service.review_document(
        session,
        document_id=document_id,
        user_id=current_user.id,
        review_status=payload.review_status,
        review_comment=payload.review_comment,
        set_active_when_approved=payload.set_active_when_approved,
    )

    latest_comment = (
        (document.content_json or {})
        .get("review", {})
        .get("latest_comment")
    )

    return DocumentReviewResponse(
        document_id=document.id,
        document_kind=document.document_kind,
        review_status=document.review_status,
        is_active=document.is_active,
        review_comment=latest_comment,
        updated_at=document.updated_at,
    )
