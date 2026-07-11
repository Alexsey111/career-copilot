# app/tasks/cover_letter_tasks.py

from __future__ import annotations

import logging
from uuid import UUID

from app.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.cover_letter_tasks.generate_cover_letter",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def generate_cover_letter(
    self,
    vacancy_id: str,
    user_id: str,
    variant: str = "standard",
) -> dict:
    import asyncio
    from app.db.session import AsyncSessionLocal
    from app.services.cover_letter_generation_service import CoverLetterGenerationService

    async def _run():
        async with AsyncSessionLocal() as session:
            service = CoverLetterGenerationService()
            document = await service.generate_cover_letter(
                session,
                vacancy_id=UUID(vacancy_id),
                user_id=UUID(user_id),
                variant=variant,
            )
            return {
                "document_id": str(document.id),
                "vacancy_id": str(document.vacancy_id),
                "version_label": document.version_label,
                "variant": variant,
                "status": "completed",
            }

    try:
        return asyncio.get_event_loop().run_until_complete(_run())
    except Exception as exc:
        logger.exception("generate_cover_letter failed", extra={"vacancy_id": vacancy_id})
        raise self.retry(exc=exc)
