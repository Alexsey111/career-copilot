# app\repositories\ai_run_repository.py

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AIRun


class AIRunRepository:
    """Репозиторий для трассировки AI-запросов"""
    
    async def create_success(
        self,
        session: AsyncSession,
        *,
        run_id: UUID,
        user_id: UUID,
        workflow_name: str,
        target_type: str,
        target_id: str | None,
        provider_name: str,
        model_name: str,
        prompt_version: str,
        input_snapshot: dict,
        output_snapshot: dict,
        duration_ms: int | None,
        tokens_used: dict | None,
    ) -> AIRun:
        """Сохраняет успешный AI-запрос"""
        ai_run = AIRun(
            id=run_id,
            user_id=user_id,
            workflow_name=workflow_name,
            target_type=target_type,
            target_id=target_id,
            status="completed",
            provider_name=provider_name,
            model_name=model_name,
            prompt_version=prompt_version,
            input_snapshot_json=input_snapshot,
            output_snapshot_json=output_snapshot,
            tokens_used_json=tokens_used,
            duration_ms=duration_ms,
        )
        session.add(ai_run)
        await session.flush()
        return ai_run
        
    async def create_error(
        self,
        session: AsyncSession,
        *,
        run_id: UUID,
        user_id: UUID,
        workflow_name: str,
        target_type: str,
        target_id: str | None,
        provider_name: str,
        model_name: str,
        prompt_version: str,
        input_snapshot: dict,
        error_text: str,
        duration_ms: int | None,
        tokens_used: dict | None = None,
    ) -> AIRun:
        """Сохраняет неудачный AI-запрос"""
        ai_run = AIRun(
            id=run_id,
            user_id=user_id,
            workflow_name=workflow_name,
            target_type=target_type,
            target_id=target_id,
            status="failed",
            provider_name=provider_name,
            model_name=model_name,
            prompt_version=prompt_version,
            input_snapshot_json=input_snapshot,
            output_snapshot_json={},
            tokens_used_json=tokens_used,
            error_text=error_text,
            duration_ms=duration_ms,
        )
        session.add(ai_run)
        await session.flush()
        return ai_run