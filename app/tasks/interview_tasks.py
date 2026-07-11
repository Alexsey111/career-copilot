# app/tasks/interview_tasks.py

from __future__ import annotations

import logging
from uuid import UUID

from app.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.interview_tasks.create_interview_prep",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def create_interview_prep(self, application_id: str, user_id: str) -> dict:
    import asyncio
    from app.db.session import AsyncSessionLocal
    from app.services.interview_prep_service import InterviewPrepService

    async def _run():
        async with AsyncSessionLocal() as session:
            service = InterviewPrepService()
            session_obj = await service.create_session(
                session,
                user_id=UUID(user_id),
                application_id=UUID(application_id),
            )
            return {
                "session_id": str(session_obj.id),
                "application_id": str(session_obj.application_id),
                "vacancy_id": str(session_obj.vacancy_id),
                "readiness_score": session_obj.readiness_score,
                "status": "completed",
            }

    try:
        return asyncio.get_event_loop().run_until_complete(_run())
    except Exception as exc:
        logger.exception("create_interview_prep failed", extra={"application_id": application_id})
        raise self.retry(exc=exc)
