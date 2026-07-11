# app/tasks/vacancy_tasks.py

from __future__ import annotations

import logging
from uuid import UUID

from app.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.vacancy_tasks.analyze_vacancy",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def analyze_vacancy(self, vacancy_id: str, user_id: str) -> dict:
    import asyncio
    from app.db.session import AsyncSessionLocal
    from app.services.vacancy_analysis_service import VacancyAnalysisService

    async def _run():
        async with AsyncSessionLocal() as session:
            service = VacancyAnalysisService()
            analysis = await service.analyze_vacancy(
                session,
                vacancy_id=UUID(vacancy_id),
                user_id=UUID(user_id),
            )
            return {
                "analysis_id": str(analysis.id),
                "vacancy_id": str(analysis.vacancy_id),
                "match_score": analysis.match_score,
                "status": "completed",
            }

    try:
        return asyncio.get_event_loop().run_until_complete(_run())
    except Exception as exc:
        logger.exception("analyze_vacancy failed", extra={"vacancy_id": vacancy_id})
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.vacancy_tasks.import_and_analyze_vacancy",
    bind=True,
    max_retries=2,
    default_retry_delay=15,
)
def import_and_analyze_vacancy(self, source_url: str, user_id: str) -> dict:
    import asyncio
    from app.db.session import AsyncSessionLocal
    from app.services.vacancy_import_service import VacancyImportService
    from app.services.vacancy_analysis_service import VacancyAnalysisService

    async def _run():
        async with AsyncSessionLocal() as session:
            import_service = VacancyImportService()
            vacancy = await import_service.import_vacancy(
                session,
                user_id=UUID(user_id),
                source="hh",
                source_url=source_url,
                external_id=None,
                title=None,
                company=None,
                location=None,
                description_raw=None,
            )

            analysis_service = VacancyAnalysisService()
            analysis = await analysis_service.analyze_vacancy(
                session,
                vacancy_id=vacancy.id,
                user_id=UUID(user_id),
            )

            return {
                "vacancy_id": str(vacancy.id),
                "analysis_id": str(analysis.id),
                "title": vacancy.title,
                "match_score": analysis.match_score,
                "status": "completed",
            }

    try:
        return asyncio.get_event_loop().run_until_complete(_run())
    except Exception as exc:
        logger.exception("import_and_analyze_vacancy failed", extra={"source_url": source_url})
        raise self.retry(exc=exc)
