"""app\api\router.py."""

from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.career_insights import router as career_insights_router
from app.api.routes.applications import router as applications_router
from app.api.routes.ai_usage import router as ai_usage_router
from app.api.routes.consent import router as consent_router
from app.api.routes.evidence import router as evidence_router
from app.api.routes.documents import router as documents_router
from app.api.routes.files import router as files_router
from app.api.routes.executions import router as executions_router
from app.api.routes.interviews import router as interviews_router
from app.api.routes.interview_prep import router as interview_prep_router
from app.api.routes.health import router as health_router
from app.api.routes.pipeline_async import router as pipeline_async_router
from app.api.routes.pipeline_execution_routes import router as pipeline_execution_router
from app.api.routes.privacy import router as privacy_router
from app.api.routes.profile import router as profile_router
from app.api.routes.review_workspace_routes import router as review_workspace_router
from app.api.routes.review_summary import router as review_summary_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.vacancies import router as vacancies_router
from app.core.config import get_settings


def build_api_router() -> APIRouter:
    settings = get_settings()

    api_router = APIRouter(prefix=settings.api_prefix)
    api_router.include_router(health_router)
    api_router.include_router(files_router)
    api_router.include_router(profile_router)
    api_router.include_router(vacancies_router)
    api_router.include_router(documents_router)
    api_router.include_router(executions_router)
    api_router.include_router(pipeline_async_router)
    api_router.include_router(auth_router)
    api_router.include_router(career_insights_router)
    api_router.include_router(applications_router)
    api_router.include_router(ai_usage_router)
    api_router.include_router(consent_router)
    api_router.include_router(privacy_router)
    api_router.include_router(evidence_router)
    api_router.include_router(interview_prep_router)
    api_router.include_router(interviews_router)
    api_router.include_router(pipeline_execution_router)
    api_router.include_router(review_workspace_router)
    api_router.include_router(review_summary_router)
    api_router.include_router(tasks_router)

    root_router = APIRouter()
    root_router.include_router(health_router)
    root_router.include_router(api_router)

    return root_router
