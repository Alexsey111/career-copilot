# app\api\routes\documents.py

from __future__ import annotations

from io import BytesIO
from uuid import UUID

from docx import Document as DocxDocument
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_ai_orchestrator, get_current_active_user
from app.ai.orchestrator import AIOrchestrator
from app.db.session import get_db_session
from app.models import User
from app.repositories.document_version_repository import DocumentVersionRepository
from app.schemas.document import (
    CoverLetterEnhanceRequest,
    CoverLetterEnhanceResponse,
    CoverLetterGenerateRequest,
    CoverLetterGenerateResponse,
    DocumentReviewRequest,
    DocumentReviewResponse,
    DocumentVersionRead,
    ResumeEnhanceRequest,
    ResumeEnhanceResponse,
    ResumeGenerateRequest,
    ResumeGenerateResponse,
)
from app.services.cover_letter_generation_service import CoverLetterGenerationService
from app.services.document_review_service import DocumentReviewService
from app.services.resume_generation_service import ResumeGenerationService


router = APIRouter(prefix="/documents", tags=["documents"])


SUPPORTED_EXPORT_FORMATS = {
    "txt": "text/plain; charset=utf-8",
    "md": "text/markdown; charset=utf-8",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _build_export_filename(
    *,
    document_kind: str,
    document_id: UUID,
    export_format: str,
) -> str:
    safe_kind = document_kind.replace("_", "-")
    return f"career-copilot-{safe_kind}-{document_id}.{export_format}"


def _build_docx_export_bytes(*, rendered_text: str) -> bytes:
    document = DocxDocument()

    for line in rendered_text.splitlines():
        document.add_paragraph(line)

    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


@router.post("/resumes/generate", response_model=ResumeGenerateResponse)
async def generate_resume(
    payload: ResumeGenerateRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
    ai: AIOrchestrator = Depends(get_ai_orchestrator),
) -> ResumeGenerateResponse:
    service = ResumeGenerationService(ai_orchestrator=ai)
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


@router.post("/resumes/{document_id}/enhance", response_model=ResumeEnhanceResponse)
async def enhance_resume(
    document_id: UUID,
    payload: ResumeEnhanceRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
    ai: AIOrchestrator = Depends(get_ai_orchestrator),
) -> ResumeEnhanceResponse:
    repo = DocumentVersionRepository()
    document = await repo.get_by_id(
        session,
        document_id,
        user_id=current_user.id,
    )
    if document is None or document.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="document not found",
        )

    service = ResumeGenerationService(ai_orchestrator=ai)
    enhanced_text = await service.enhance_resume_with_ai(
        session,
        user_id=current_user.id,
        resume_text=payload.resume_text,
    )

    return ResumeEnhanceResponse(
        document_id=document.id,
        vacancy_id=document.vacancy_id,
        review_status=document.review_status,
        version_label=document.version_label,
        created_at=document.created_at,
        enhanced_text=enhanced_text,
    )


@router.post("/letters/generate", response_model=CoverLetterGenerateResponse)
async def generate_cover_letter(
    payload: CoverLetterGenerateRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
    ai: AIOrchestrator = Depends(get_ai_orchestrator),
) -> CoverLetterGenerateResponse:
    service = CoverLetterGenerationService(ai_orchestrator=ai)
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


@router.post("/letters/{document_id}/enhance", response_model=CoverLetterEnhanceResponse)
async def enhance_cover_letter(
    document_id: UUID,
    payload: CoverLetterEnhanceRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
    ai: AIOrchestrator = Depends(get_ai_orchestrator),
) -> CoverLetterEnhanceResponse:
    repo = DocumentVersionRepository()
    document = await repo.get_by_id(
        session,
        document_id,
        user_id=current_user.id,
    )
    if document is None or document.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="document not found",
        )

    service = CoverLetterGenerationService(ai_orchestrator=ai)
    enhanced_text = await service.enhance_cover_letter_with_ai(
        session,
        user_id=current_user.id,
        draft_text=payload.cover_letter_text,
    )

    return CoverLetterEnhanceResponse(
        document_id=document.id,
        vacancy_id=document.vacancy_id,
        review_status=document.review_status,
        version_label=document.version_label,
        created_at=document.created_at,
        enhanced_text=enhanced_text,
    )


@router.get("/{document_id}", response_model=DocumentVersionRead)
async def get_document(
    document_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> DocumentVersionRead:
    repo = DocumentVersionRepository()
    document = await repo.get_by_id(
        session,
        document_id,
        user_id=current_user.id,
    )
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
        analysis_id=document.analysis_id,
        document_kind=document.document_kind,
        version_label=document.version_label,
        review_status=document.review_status,
        is_active=document.is_active,
        rendered_text=document.rendered_text,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@router.get("/{document_id}/export/{export_format}")
async def export_document(
    document_id: UUID,
    export_format: str,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    normalized_format = export_format.lower().strip()

    if normalized_format not in SUPPORTED_EXPORT_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="unsupported export format; use txt, md or docx",
        )

    repo = DocumentVersionRepository()
    document = await repo.get_by_id(
        session,
        document_id,
        user_id=current_user.id,
    )

    if document is None or document.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="document not found",
        )

    if document.review_status != "approved" or not document.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="document must be approved and active before export",
        )

    if not document.rendered_text:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="document has no rendered text to export",
        )

    filename = _build_export_filename(
        document_kind=document.document_kind,
        document_id=document.id,
        export_format=normalized_format,
    )

    if normalized_format == "docx":
        content = _build_docx_export_bytes(rendered_text=document.rendered_text)
    else:
        content = document.rendered_text

    return Response(
        content=content,
        media_type=SUPPORTED_EXPORT_FORMATS[normalized_format],
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.patch("/{document_id}/review", response_model=DocumentReviewResponse)
async def review_document(
    document_id: UUID,
    payload: DocumentReviewRequest,
    current_user: User = Depends(get_current_active_user),
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
