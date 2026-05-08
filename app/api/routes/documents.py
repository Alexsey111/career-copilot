# app\api\routes\documents.py

from __future__ import annotations

from datetime import datetime
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
    ActiveDocumentResponse,
    CoverLetterEnhanceRequest,
    CoverLetterEnhanceResponse,
    CoverLetterGenerateRequest,
    CoverLetterGenerateResponse,
    DocumentActivateResponse,
    DocumentDiffResponse,
    DocumentHistoryItem,
    DocumentHistoryResponse,
    DocumentReviewRequest,
    DocumentReviewResponse,
    DocumentRollbackResponse,
    DocumentVersionRead,
    ResumeEnhanceRequest,
    ResumeEnhanceResponse,
    ResumeGenerateRequest,
    ResumeGenerateResponse,
)
from app.services.document_activation_service import (
    DocumentActivationService,
)
from app.services.document_rollback_service import (
    DocumentRollbackService,
)
from app.services.document_diff_service import DocumentDiffService
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

    await session.commit()

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

    # --- NEW: diff ---
    diff = service._compute_diff(
        document.rendered_text or "",
        enhanced_text,
    )

    # --- NEW: content_json clone ---
    new_content = dict(document.content_json or {})
    meta = dict(new_content.get("meta", {}))
    meta["enhanced_from"] = str(document.id)
    meta["diff_from_previous"] = diff
    new_content["meta"] = meta

    # --- NEW: create version ---
    new_document = await repo.create(
        session,
        user_id=current_user.id,
        vacancy_id=document.vacancy_id,
        derived_from_id=document.id,
        analysis_id=document.analysis_id,
        document_kind=document.document_kind,
        version_label="resume_enhanced_v1",
        review_status="draft",
        is_active=False,
        content_json=new_content,
        rendered_text=enhanced_text,
    )

    await session.commit()
    await session.refresh(new_document)

    return ResumeEnhanceResponse(
        document_id=new_document.id,
        vacancy_id=new_document.vacancy_id,
        review_status=new_document.review_status,
        version_label=new_document.version_label,
        created_at=new_document.created_at,
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

    await session.commit()

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


@router.get(
    "/active",
    response_model=ActiveDocumentResponse,
)
async def get_active_document(
    document_kind: str,
    vacancy_id: UUID | None = None,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> ActiveDocumentResponse:
    repo = DocumentVersionRepository()

    document = await repo.get_active_for_scope(
        session,
        user_id=current_user.id,
        vacancy_id=vacancy_id,
        document_kind=document_kind,
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="active document not found",
        )

    return ActiveDocumentResponse(
        id=document.id,
        vacancy_id=document.vacancy_id,
        document_kind=document.document_kind,
        version_label=document.version_label,
        review_status=document.review_status,
        is_active=document.is_active,
        created_at=document.created_at,
        updated_at=document.updated_at,
        rendered_text=document.rendered_text,
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


@router.get("/{document_id}/history", response_model=DocumentHistoryResponse)
async def get_document_history(
    document_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> DocumentHistoryResponse:
    repo = DocumentVersionRepository()

    # 1. Берём текущий документ
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

    # 2. Загружаем весь scope
    documents = await repo.list_for_scope(
        session,
        user_id=current_user.id,
        vacancy_id=document.vacancy_id,
        document_kind=document.document_kind,
    )

    docs_by_id = {doc.id: doc for doc in documents}
    depth_cache: dict[UUID, int] = {}

    def _version_depth(version_id: UUID) -> int:
        cached = depth_cache.get(version_id)
        if cached is not None:
            return cached

        current = docs_by_id.get(version_id)
        if current is None or current.derived_from_id is None:
            depth_cache[version_id] = 0
            return 0

        depth = 1 + _version_depth(current.derived_from_id)
        depth_cache[version_id] = depth
        return depth

    documents = sorted(
        documents,
        key=lambda doc: (
            _version_depth(doc.id),
            doc.created_at,
            doc.updated_at,
        ),
        reverse=True,
    )

    items = [
        DocumentHistoryItem(
            id=doc.id,
            derived_from_id=doc.derived_from_id,
            version_label=doc.version_label,
            review_status=doc.review_status,
            is_active=doc.is_active,
            created_at=doc.created_at,
        )
        for doc in documents
    ]

    return DocumentHistoryResponse(items=items)


@router.post("/{document_id}/activate", response_model=DocumentActivateResponse)
async def activate_document(
    document_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> DocumentActivateResponse:
    service = DocumentActivationService()

    document = await service.activate_document(
        session,
        document_id=document_id,
        user_id=current_user.id,
    )

    activated_at = (
        (document.content_json or {})
        .get("activation", {})
        .get("last_activated_at")
    )

    return DocumentActivateResponse(
        document_id=document.id,
        document_kind=document.document_kind,
        is_active=document.is_active,
        activated_at=datetime.fromisoformat(activated_at),
    )


@router.post(
    "/{document_id}/rollback",
    response_model=DocumentRollbackResponse,
)
async def rollback_document(
    document_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> DocumentRollbackResponse:
    service = DocumentRollbackService()

    document = await service.rollback_document(
        session,
        source_document_id=document_id,
        user_id=current_user.id,
    )

    return DocumentRollbackResponse(
        document_id=document.id,
        source_document_id=document_id,
        document_kind=document.document_kind,
        is_active=document.is_active,
        created_at=document.created_at,
    )


@router.get("/{document_id}/diff/{other_document_id}", response_model=DocumentDiffResponse)
async def diff_documents(
    document_id: UUID,
    other_document_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> DocumentDiffResponse:
    service = DocumentDiffService()

    result = await service.build_diff(
        session,
        user_id=current_user.id,
        document_id=document_id,
        other_document_id=other_document_id,
    )

    return DocumentDiffResponse(
        document_id=result["document_id"],
        other_document_id=result["other_document_id"],
        document_kind=result["document_kind"],
        diff=result["diff"],
    )
