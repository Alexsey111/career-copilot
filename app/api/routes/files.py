# app\api\routes\files.py

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_dev_user
from app.db.session import get_db_session
from app.models import User
from app.schemas.source_file import SourceFileRead
from app.services.source_file_service import SourceFileService


router = APIRouter(prefix="/files", tags=["files"])


@router.post("/upload", response_model=SourceFileRead)
async def upload_file(
    file_kind: str = Form("resume"),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_dev_user),
    session: AsyncSession = Depends(get_db_session),
) -> SourceFileRead:
    service = SourceFileService()
    source_file = await service.upload_source_file(
        session,
        user_id=current_user.id,
        file_kind=file_kind,
        upload_file=file,
    )
    return SourceFileRead.model_validate(source_file)


@router.get("/{file_id}", response_model=SourceFileRead)
async def get_file(
    file_id: UUID,
    current_user: User = Depends(get_current_dev_user),
    session: AsyncSession = Depends(get_db_session),
) -> SourceFileRead:
    service = SourceFileService()
    source_file = await service.get_source_file(
        session,
        file_id=file_id,
        user_id=current_user.id,
    )
    return SourceFileRead.model_validate(source_file)
