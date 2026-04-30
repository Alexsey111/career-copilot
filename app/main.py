"""app\main.py."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.router import build_api_router
from app.api.routes.interviews import router as interviews_router
from app.core.config import get_settings
from app.core.logging import setup_logging


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        debug=settings.app_debug,
        lifespan=lifespan,
    )

    @app.get("/", tags=["root"])
    async def root() -> JSONResponse:
        return JSONResponse(
            {
                "service": settings.app_name,
                "status": "ok",
            }
        )

    app.include_router(build_api_router())
    app.include_router(interviews_router, prefix="/api/v1")
    return app


app = create_app()
