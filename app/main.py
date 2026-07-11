"""app/main.py."""

from contextlib import asynccontextmanager
import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from app.api.error_handlers import register_error_handlers
from app.api.router import build_api_router
from app.core.config import get_settings
from app.core.error_monitoring import setup_error_monitoring
from app.core.logging import setup_logging
from app.core.tracing import (
    clear_trace_context,
    get_trace_context,
    new_correlation_id,
    set_trace_context,
)

try:
    from prometheus_client import (
        Counter,
        Histogram,
        generate_latest,
        CONTENT_TYPE_LATEST,
    )
    REQUEST_COUNT = Counter(
        "career_copilot_requests_total",
        "Total requests",
        ["method", "endpoint", "status"],
    )
    REQUEST_LATENCY = Histogram(
        "career_copilot_request_duration_seconds",
        "Request latency",
        ["method", "endpoint"],
        buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    setup_error_monitoring()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    request_logger = logging.getLogger("app.request")

    app = FastAPI(
        title=settings.app_name,
        debug=settings.app_debug,
        lifespan=lifespan,
    )
    register_error_handlers(app)

    # TrustedHostMiddleware hardens against Host-header attacks. Defaults to
    # ["*"] (no-op) in dev; prod deploy sets ALLOWED_HOSTS to real hosts.
    if settings.allowed_hosts and settings.allowed_hosts != ["*"]:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Correlation-ID", "X-Request-ID"],
        expose_headers=["X-Correlation-ID", "X-Trace-ID"],
    )

    @app.middleware("http")
    async def trace_context_middleware(request: Request, call_next):
        start_time = time.perf_counter()
        correlation_id = (
            request.headers.get("x-correlation-id")
            or request.headers.get("x-request-id")
            or new_correlation_id()
        )
        set_trace_context(trace_id=correlation_id, correlation_id=correlation_id)
        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            request_logger.info(
                "http_request_completed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                    "correlation_id": correlation_id,
                },
            )

            if PROMETHEUS_AVAILABLE:
                REQUEST_COUNT.labels(
                    method=request.method,
                    endpoint=request.url.path,
                    status=response.status_code,
                ).inc()
                REQUEST_LATENCY.labels(
                    method=request.method,
                    endpoint=request.url.path,
                ).observe(duration_ms / 1000)

            response.headers["X-Correlation-ID"] = correlation_id
            active_trace_id = get_trace_context().trace_id
            if active_trace_id:
                response.headers["X-Trace-ID"] = active_trace_id
            # HSTS: instruct browsers to use HTTPS for this host for 1 year.
            # TLS itself is terminated at the upstream proxy; this header
            # enforces HTTPS on the client side in production (ФЗ-152 ст.19).
            if settings.is_production:
                response.headers["Strict-Transport-Security"] = (
                    "max-age=31536000; includeSubDomains"
                )
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

    if PROMETHEUS_AVAILABLE:
        @app.get("/metrics", tags=["observability"])
        async def metrics():
            return PlainTextResponse(
                generate_latest(),
                media_type=CONTENT_TYPE_LATEST,
            )

    app.include_router(build_api_router())
    return app


app = create_app()
