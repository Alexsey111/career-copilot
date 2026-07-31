# app\api\routes\documents.py

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
from uuid import UUID

from docx import Document as DocxDocument
from fastapi import APIRouter, Depends, HTTPException, Response, status
from fpdf import FPDF
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_ai_orchestrator,
    get_current_active_user,
    require_ai_consent,
    require_quota,
)
from app.ai.orchestrator import AIOrchestrator
from app.db.session import get_db_session
from app.models import User
from app.repositories.document_version_repository import DocumentVersionRepository
from app.repositories.review_workflow_repository import ReviewWorkflowRepository
from app.schemas.document import (
    ActiveDocumentResponse,
    CoverLetterEnhanceRequest,
    CoverLetterEnhanceResponse,
    CoverLetterGenerateRequest,
    CoverLetterGenerateResponse,
    DocumentActivateResponse,
    DocumentDiffResponse,
    DocumentHistoryResponse,
    DocumentListItem,
    DocumentListResponse,
    DocumentReadinessResponse,
    DocumentReviewSummaryResponse,
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
from app.services.document_review_summary_service import DocumentReviewSummaryService
from app.services.document_review_service import DocumentReviewService
from app.services.resume_generation_service import ResumeGenerationService
from app.services.readiness_gate_service import ReadinessGateService


router = APIRouter(prefix="/documents", tags=["documents"])


SUPPORTED_EXPORT_FORMATS = {
    "txt": "text/plain; charset=utf-8",
    "md": "text/markdown; charset=utf-8",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
}

# Unicode TTF (DejaVu Sans, OFL) с полной кириллицей — bundled в репозитории,
# чтобы PDF-экспорт работал и на Windows, и в Docker без системных шрифтов.
# Core-шрифты fpdf2 (Helvetica) — latin-1, кириллицу не поддерживают.
_BUNDLED_FONT_PATH = Path(__file__).resolve().parent.parent.parent / "assets" / "fonts" / "DejaVuSans.ttf"


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

    # Этап 8: sanitization метаданных DOCX. python-docx пишет core_properties
    # (author/last_modified_by/title/...) — туда может утекать имя процесса/ОС
    # или автора исходного резюме. Обнуляем перед save (ФЗ-152 ст.19 + репутационный
    # риск: экспортируемый файл не должен нести лишних ПДн).
    cp = document.core_properties
    for attr in (
        "author",
        "last_modified_by",
        "title",
        "subject",
        "keywords",
        "comments",
        "category",
        "content_status",
        "identifier",
        "language",
        "version",
    ):
        try:
            setattr(cp, attr, "")
        except Exception:  # pragma: no cover - defensive
            pass

    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _build_pdf_export_bytes(*, rendered_text: str) -> bytes:
    """PDF из отрендеренного текста документа.

    Использует bundled DejaVu Sans (OFL) — единственный надёжный способ
    корректно отрисовать кириллицу без системных шрифтов (Windows/Docker).
    ``rendered_text`` — plain-text с переносами строк (как ``resume_renderer``
    формирует для txt/md); Markdown-разметка не интерпретируется (как и в txt).

    Перенос строк делается вручную по измерению ширины (``get_string_width``) с
    посимвольным накоплением и ``cell`` на каждую визуальную строку. Это
    детерминированно и не падает/не зависает на длинных неразрывных токенах
    (URL, длинное слово) — в отличие от ``multi_cell`` word-wrap'а fpdf2
    (``FPDFException: Not enough horizontal space``) и ``wrapmode="CHAR"``
    (зависает на многих строках с auto_page_break).
    """
    if not _BUNDLED_FONT_PATH.exists():  # pragma: no cover - defensive
        raise RuntimeError(
            f"bundled font not found: {_BUNDLED_FONT_PATH} "
            "(re-add app/assets/fonts/DejaVuSans.ttf)"
        )

    pdf = FPDF(format="A4")
    # Поля задаём ДО add_page — иначе epw (ширина текста) посчитается по умолчанию.
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.add_font("DejaVu", "", str(_BUNDLED_FONT_PATH))
    pdf.set_font("DejaVu", size=11)

    avail_width = pdf.epw  # эффективная ширина текста (A4 − поля)

    for line in rendered_text.splitlines():
        if not line:
            pdf.ln(4)
            continue
        # Жадный посимвольный перенос: accum chars, пока ширина ≤ avail_width.
        buf = ""
        for ch in line:
            if pdf.get_string_width(buf + ch) <= avail_width:
                buf += ch
            else:
                pdf.cell(0, 6, buf, new_x="LEFT", new_y="NEXT")
                buf = ch
        if buf:
            pdf.cell(0, 6, buf, new_x="LEFT", new_y="NEXT")

    out = pdf.output()
    return bytes(out)


def _snapshot_to_history_item(snapshot):
    from app.schemas.document import DocumentSnapshotHistoryItem

    return DocumentSnapshotHistoryItem(
        id=snapshot.id,
        created_at=snapshot.created_at,
        derived_from_id=snapshot.derived_from_id,
        version_label=snapshot.version_label,
        review_status=snapshot.review_status,
        is_active=snapshot.is_active,
    )


@router.post("/resumes/generate", response_model=ResumeGenerateResponse)
async def generate_resume(
    payload: ResumeGenerateRequest,
    current_user: User = Depends(require_ai_consent),
    session: AsyncSession = Depends(get_db_session),
    ai: AIOrchestrator = Depends(get_ai_orchestrator),
    _quota: User = Depends(require_quota("generated_output")),
) -> ResumeGenerateResponse:
    service = ResumeGenerationService(ai_orchestrator=ai)
    document = await service.generate_resume(
        session,
        vacancy_id=payload.vacancy_id,
        user_id=current_user.id,
        market=payload.market,
    )

    try:
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
    except Exception:
        await session.rollback()
        raise


@router.post("/resumes/{document_id}/enhance", response_model=ResumeEnhanceResponse)
async def enhance_resume(
    document_id: UUID,
    payload: ResumeEnhanceRequest,
    current_user: User = Depends(require_ai_consent),
    session: AsyncSession = Depends(get_db_session),
    ai: AIOrchestrator = Depends(get_ai_orchestrator),
    _quota: User = Depends(require_quota("ai_request")),
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
    try:
        enhancement = await service.enhance_resume_with_ai(
            session,
            user_id=current_user.id,
            resume_text=payload.resume_text,
        )
    except HTTPException:
        # Quota/permission/etc. — пробрасываем без отката собственного
        # состояния, но без commit (autoflush=False).
        raise

    # ``enhance_resume_with_ai`` уже списал токены (AIRun записан
    # через ``trace_ai_run`` в orchestrator) и вернул ``degraded=True``,
    # если safety/factuality-gate отбросил результат. В этом случае мы НЕ
    # создаём новый DocumentVersion и НЕ возвращаем 200 — иначе пользователь
    # увидит «AI улучшил» + списание без видимого эффекта (Bug#102).
    if enhancement.get("degraded"):
        await session.commit()  # фиксируем AIRun (метринг) и его error_text
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "ai_enhancement_rejected",
                "reason": enhancement.get("reason") or "unknown",
                "message": (
                    "AI не смог улучшить текст резюме без потери смысла. "
                    "Токены списаны за попытку; исходный текст остался без изменений."
                ),
            },
        )

    enhanced_text = enhancement["text"]

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

    try:
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
    except Exception:
        await session.rollback()
        raise


@router.post("/letters/generate", response_model=CoverLetterGenerateResponse)
async def generate_cover_letter(
    payload: CoverLetterGenerateRequest,
    current_user: User = Depends(require_ai_consent),
    session: AsyncSession = Depends(get_db_session),
    ai: AIOrchestrator = Depends(get_ai_orchestrator),
    _quota: User = Depends(require_quota("generated_output")),
) -> CoverLetterGenerateResponse:
    service = CoverLetterGenerationService(ai_orchestrator=ai)
    document = await service.generate_cover_letter(
        session,
        vacancy_id=payload.vacancy_id,
        user_id=current_user.id,
        variant=payload.variant,
    )

    try:
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
    except Exception:
        await session.rollback()
        raise


@router.post("/letters/{document_id}/enhance", response_model=CoverLetterEnhanceResponse)
async def enhance_cover_letter(
    document_id: UUID,
    payload: CoverLetterEnhanceRequest,
    current_user: User = Depends(require_ai_consent),
    session: AsyncSession = Depends(get_db_session),
    ai: AIOrchestrator = Depends(get_ai_orchestrator),
    _quota: User = Depends(require_quota("ai_request")),
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
    try:
        enhancement = await service.enhance_cover_letter_with_ai(
            session,
            user_id=current_user.id,
            draft_text=payload.cover_letter_text,
        )
    except HTTPException:
        # Quota/permission/etc. — пробрасываем без отката собственного
        # состояния, но без commit (autoflush=False).
        raise

    # ``enhance_cover_letter_with_ai`` уже списал токены (AIRun записан
    # через ``trace_ai_run`` в orchestrator) и вернул ``degraded=True``,
    # если safety/factuality-gate отбросил результат. В этом случае мы НЕ
    # создаём новый DocumentVersion и НЕ возвращаем 200 — иначе пользователь
    # увидит «AI улучшил» + списание без видимого эффекта (Bug#74).
    if enhancement.get("degraded"):
        await session.commit()  # фиксируем AIRun (метринг) и его error_text
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "ai_enhancement_rejected",
                "reason": enhancement.get("reason") or "unknown",
                "message": (
                    "AI не смог улучшить текст письма без потери смысла. "
                    "Токены списаны за попытку; исходный текст остался без изменений."
                ),
            },
        )

    enhanced_text = enhancement["text"]

    new_content = dict(document.content_json or {})
    meta = dict(new_content.get("meta", {}))
    meta["enhanced_from"] = str(document.id)
    meta["diff_from_previous"] = {
        "rendered_text_changed": enhanced_text != (document.rendered_text or ""),
        "source_document_id": str(document.id),
    }
    new_content["meta"] = meta

    new_document = await repo.create(
        session,
        user_id=current_user.id,
        vacancy_id=document.vacancy_id,
        derived_from_id=document.id,
        analysis_id=document.analysis_id,
        document_kind=document.document_kind,
        version_label="cover_letter_enhanced_v1",
        review_status="draft",
        is_active=False,
        content_json=new_content,
        rendered_text=enhanced_text,
    )

    try:
        await session.commit()
    except Exception:
        await session.rollback()
        raise

    return CoverLetterEnhanceResponse(
        document_id=new_document.id,
        vacancy_id=new_document.vacancy_id,
        review_status=new_document.review_status,
        version_label=new_document.version_label,
        created_at=new_document.created_at,
        enhanced_text=enhanced_text,
    )


@router.get(
    "",
    response_model=DocumentListResponse,
)
async def list_documents(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> DocumentListResponse:
    """Список документов пользователя (любой kind/vacancy), свежие сверху.

    Нужен селектору панели доверия: ``GET /documents/active`` возвращает только
    ``is_active``-версию конкретного kind и 404, если её нет — селектор
    оказывался пустым при наличии созданных, но не активированных документов.
    """
    repo = DocumentVersionRepository()
    documents = await repo.list_by_user(session, user_id=current_user.id, limit=100)
    items = [
        DocumentListItem(
            id=doc.id,
            vacancy_id=doc.vacancy_id,
            document_kind=doc.document_kind,
            version_label=doc.version_label,
            review_status=doc.review_status,
            is_active=doc.is_active,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )
        for doc in documents
    ]
    return DocumentListResponse(items=items, total=len(items))


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


@router.get("/{document_id}/readiness", response_model=DocumentReadinessResponse)
async def get_document_readiness(
    document_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> DocumentReadinessResponse:
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

    readiness = ReadinessGateService().evaluate_document_readiness(document)
    return DocumentReadinessResponse(
        ready=readiness.ready,
        blockers=readiness.blockers,
        warnings=readiness.warnings,
        score=readiness.score,
    )


@router.get("/{document_id}/review-summary", response_model=DocumentReviewSummaryResponse)
async def get_document_review_summary(
    document_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> DocumentReviewSummaryResponse:
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

    service = DocumentReviewSummaryService()
    summary = service.build_summary(document)
    preview = (document.rendered_text or "")[:1200] or None

    return DocumentReviewSummaryResponse(
        document_id=document.id,
        document_kind=document.document_kind,
        review_status=document.review_status,
        is_active=document.is_active,
        version_label=document.version_label,
        readiness=DocumentReadinessResponse.model_validate(summary["readiness"]),
        quality=summary["quality"],
        provenance=summary["provenance"],
        claims_needing_confirmation=summary["claims_needing_confirmation"],
        warnings=summary["warnings"],
        selected_achievements=summary["selected_achievements"],
        selected_achievement_ids=summary["selected_achievement_ids"],
        selected_evidence_ids=summary["selected_evidence_ids"],
        evidence_selection_reason=summary["evidence_selection_reason"],
        selected_evidence=summary["selected_evidence"],
        unused_evidence=summary["unused_evidence"],
        matched_keywords=summary["matched_keywords"],
        missing_keywords=summary["missing_keywords"],
        selection_rationale=summary["selection_rationale"],
        rendered_text_preview=preview,
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
            detail="unsupported export format; use txt, md, docx or pdf",
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
    elif normalized_format == "pdf":
        content = _build_pdf_export_bytes(rendered_text=document.rendered_text)
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
    service = DocumentReviewService(
        review_workflow_repository=ReviewWorkflowRepository(),
    )
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

    # 2. Загружаем весь scope document versions
    documents = await repo.list_for_scope(
        session,
        user_id=current_user.id,
        vacancy_id=document.vacancy_id,
        document_kind=document.document_kind,
    )

    docs_by_id = {doc.id: doc for doc in documents}
    children_map: dict[UUID, list] = {}
    for doc in documents:
        if doc.derived_from_id is not None:
            children_map.setdefault(doc.derived_from_id, []).append(doc)
    for children in children_map.values():
        children.sort(key=lambda item: item.created_at)

    def _lineage(version_id: UUID) -> list:
        lineage: list = []
        current = docs_by_id.get(version_id)
        visited: set[UUID] = set()
        while current is not None and current.id not in visited:
            visited.add(current.id)
            lineage.append(current)
            if current.derived_from_id is None:
                break
            current = docs_by_id.get(current.derived_from_id)
        lineage.reverse()
        return lineage

    branch_heads = [doc for doc in documents if doc.id not in children_map]
    branches = [
        {
            "head_snapshot_id": head.id,
            "snapshots": [_snapshot_to_history_item(doc).model_dump() for doc in _lineage(head.id)],
        }
        for head in branch_heads
    ]

    snapshot_items = [_snapshot_to_history_item(doc) for doc in documents]
    latest = snapshot_items[0] if snapshot_items else None
    comparison = None
    if len(documents) >= 2:
        diff_service = DocumentDiffService()
        diff_result = await diff_service.build_diff(
            session,
            user_id=current_user.id,
            document_id=documents[0].id,
            other_document_id=documents[1].id,
        )
        comparison = {
            "from_document_id": diff_result["base_document_id"],
            "to_document_id": diff_result["target_document_id"],
            "diff": diff_result["summary"],
        }

    return DocumentHistoryResponse(
        snapshots=snapshot_items,
        branches=branches,
        latest=latest,
        comparison=comparison,
        items=snapshot_items,
    )


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
        base_document_id=result["base_document_id"],
        target_document_id=result["target_document_id"],
        document_kind=result["document_kind"],
        sections=result["sections"],
    )
