# app/tasks/resume_tasks.py

from __future__ import annotations

import logging
from uuid import UUID

from app.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.resume_tasks.generate_resume",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def generate_resume(self, vacancy_id: str, user_id: str, market: str | None = None) -> dict:
    import asyncio
    from app.db.session import AsyncSessionLocal
    from app.services.resume_generation_service import ResumeGenerationService

    async def _run():
        async with AsyncSessionLocal() as session:
            service = ResumeGenerationService()
            document = await service.generate_resume(
                session,
                vacancy_id=UUID(vacancy_id),
                user_id=UUID(user_id),
                market=market,
            )
            return {
                "document_id": str(document.id),
                "vacancy_id": str(document.vacancy_id),
                "version_label": document.version_label,
                "status": "completed",
            }

    try:
        return asyncio.get_event_loop().run_until_complete(_run())
    except Exception as exc:
        logger.exception("generate_resume failed", extra={"vacancy_id": vacancy_id})
        raise self.retry(exc=exc)
