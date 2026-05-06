# app\api\ai\tracing.py

from __future__ import annotations

from typing import Any
from uuid import UUID


async def trace_ai_run(
    session: Any,  # AsyncSession
    *,
    run_id: UUID,
    user_id: UUID,
    workflow_name: str,
    target_type: str,
    target_id: str | None,
    model_name: str,
    prompt_version: str,
    input_snapshot: dict[str, Any],
    output_snapshot: dict[str, Any] | None = None,
    error_text: str | None = None,
    duration_ms: int | None = None,
    tokens_used: dict[str, int] | None = None,
) -> None:
    """
    Универсальная функция трассировки AI-запросов.
    Делегирует репозиторию для сохранения в БД.
    """
    from app.repositories.ai_run_repository import AIRunRepository
    
    repo = AIRunRepository()
    
    if error_text:
        await repo.create_error(
            session,
            run_id=run_id,
            user_id=user_id,
            workflow_name=workflow_name,
            target_type=target_type,
            target_id=target_id,
            model_name=model_name,
            prompt_version=prompt_version,
            input_snapshot=input_snapshot,
            error_text=error_text,
            duration_ms=duration_ms,
        )
    else:
        await repo.create_success(
            session,
            run_id=run_id,
            user_id=user_id,
            workflow_name=workflow_name,
            target_type=target_type,
            target_id=target_id,
            model_name=model_name,
            prompt_version=prompt_version,
            input_snapshot=input_snapshot,
            output_snapshot=output_snapshot or {},
            duration_ms=duration_ms,
            tokens_used=tokens_used or {},
        )