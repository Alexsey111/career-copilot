"""API error handlers."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.exceptions import AppError
from app.core.tracing import get_trace_context

logger = logging.getLogger("app.errors")


def _correlation_id_from_request(request: Request) -> str | None:
    context = get_trace_context()
    return (
        context.correlation_id
        or request.headers.get("x-correlation-id")
        or request.headers.get("x-request-id")
    )


def _error_response(
    *,
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | list[Any] | None = None,
    legacy_detail: Any | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    correlation_id = _correlation_id_from_request(request)

    payload: dict[str, Any] = {
        "detail": message if legacy_detail is None else legacy_detail,
        "error": {
            "code": code,
            "message": message,
            "correlation_id": correlation_id,
            "details": details or {},
        }
    }

    response = JSONResponse(
        status_code=status_code,
        content=payload,
        headers=headers,
    )

    if correlation_id:
        response.headers["X-Correlation-ID"] = correlation_id

    return response


def _http_error_code(status_code: int) -> str:
    return {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        413: "payload_too_large",
        422: "validation_error",
    }.get(status_code, "http_error")


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.warning(
        "app_error",
        extra={
            "code": exc.code,
            "status_code": exc.status_code,
            "path": request.url.path,
        },
    )

    return _error_response(
        request=request,
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details,
        legacy_detail=exc.details,
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, str) else "HTTP error"

    return _error_response(
        request=request,
        status_code=exc.status_code,
        code=_http_error_code(exc.status_code),
        message=detail,
        legacy_detail=exc.detail,
        headers=exc.headers,
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    logger.warning(
        "validation_error",
        extra={
            "path": request.url.path,
            "error_count": len(exc.errors()),
        },
    )

    return _error_response(
        request=request,
        status_code=422,
        code="validation_error",
        message="Request validation failed",
        details={"errors": exc.errors()},
        legacy_detail="Request validation failed",
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    logger.exception(
        "unhandled_exception",
        extra={
            "path": request.url.path,
            "exception_type": type(exc).__name__,
        },
    )

    return _error_response(
        request=request,
        status_code=500,
        code="internal_server_error",
        message="Internal server error",
        legacy_detail="Internal server error",
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
