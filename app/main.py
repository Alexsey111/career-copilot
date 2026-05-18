"""app/main.py."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.router import build_api_router
from app.api.routes.interviews import router as interviews_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.tracing import (
    clear_trace_context,
    get_trace_context,
    new_correlation_id,
    set_trace_context,
)


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

    @app.middleware("http")
    async def trace_context_middleware(request: Request, call_next):
        correlation_id = (
            request.headers.get("x-correlation-id")
            or request.headers.get("x-request-id")
            or new_correlation_id()
        )
        set_trace_context(trace_id=correlation_id, correlation_id=correlation_id)
        try:
            response = await call_next(request)
            response.headers["X-Correlation-ID"] = correlation_id
            active_trace_id = get_trace_context().trace_id
            if active_trace_id:
                response.headers["X-Trace-ID"] = active_trace_id
            return response
        finally:
            clear_trace_context()

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
