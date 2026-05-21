# app\core\tracing.py

from __future__ import annotations

from dataclasses import dataclass
from contextvars import ContextVar
from typing import Any
from uuid import UUID, uuid4

from app.domain.execution_event_payloads import serialize_execution_event_payload

try:  # pragma: no cover - optional dependency wiring
    from structlog.contextvars import bind_contextvars, clear_contextvars
except ModuleNotFoundError:  # pragma: no cover - fallback when structlog helpers are unavailable
    bind_contextvars = None
    clear_contextvars = None


@dataclass(slots=True, frozen=True)
class TraceContext:
    trace_id: str | None = None
    correlation_id: str | None = None

_trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)
_correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def set_trace_context(*, trace_id: str | UUID | None = None, correlation_id: str | None = None) -> TraceContext:
    """Bind trace identifiers for the current request/job."""
    if trace_id is not None:
        _trace_id_var.set(str(trace_id))
    if correlation_id is not None:
        _correlation_id_var.set(str(correlation_id))

    if bind_contextvars is not None:
        context: dict[str, Any] = {}
        if trace_id is not None:
            context["trace_id"] = str(trace_id)
        if correlation_id is not None:
            context["correlation_id"] = str(correlation_id)
        if context:
            bind_contextvars(**context)

    return get_trace_context()


def clear_trace_context() -> None:
    """Clear the current trace context."""
    _trace_id_var.set(None)
    _correlation_id_var.set(None)

    if clear_contextvars is not None:
        clear_contextvars()


def get_trace_context() -> TraceContext:
    """Return the active trace context."""
    return TraceContext(trace_id=_trace_id_var.get(), correlation_id=_correlation_id_var.get())


def new_correlation_id() -> str:
    """Generate a stable request/job correlation identifier."""
    return uuid4().hex


def enrich_execution_event_payload(
    execution_id: UUID,
    payload: Any | None = None,
    *,
    trace_id: str | UUID | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Add trace metadata to an execution event payload."""
    enriched_payload = serialize_execution_event_payload(payload)
    context = get_trace_context()

    enriched_payload["execution_id"] = str(execution_id)
    enriched_payload["trace_id"] = str(trace_id or execution_id)

    active_correlation_id = correlation_id or context.correlation_id
    if active_correlation_id:
        enriched_payload["correlation_id"] = str(active_correlation_id)

    return enriched_payload
