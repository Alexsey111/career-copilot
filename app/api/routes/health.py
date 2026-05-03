"""Health check route placeholder."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.engine import make_url

from app.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/db-info")
async def db_info() -> dict[str, str | int | None]:
    settings = get_settings()

    if settings.app_env not in {"local", "dev", "development", "test"}:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )

    url = make_url(settings.database_url)

    return {
        "environment": settings.app_env,
        "db_driver": url.drivername,
        "db_host": url.host,
        "db_port": url.port,
        "db_name": url.database,
    }
