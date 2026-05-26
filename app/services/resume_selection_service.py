from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SourceFile
from app.repositories.source_file_repository import SourceFileRepository


class ResumeSelectionService:
    def __init__(
        self,
        *,
        source_file_repository: SourceFileRepository | None = None,
    ) -> None:
        self.source_file_repository = source_file_repository or SourceFileRepository()

    async def get_active_resume(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
    ) -> SourceFile | None:
        return await self.source_file_repository.get_active_by_kind(
            session,
            user_id=user_id,
            file_kind="resume",
        )
