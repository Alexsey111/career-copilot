"""
Ручной скрипт для тестирования AIOrchestrator с реальным GigaChat API.

Запуск:
    cd "d:/python projects/career-copilot"
    python -m scripts.test_orchestrator_manual

Требует:
    - GIGACHAT_API_KEY в .env
    - БД доступна (для трассировки AI_RUNS)
    - Хотя бы один пользователь в таблице users
"""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.core.config import get_settings
from app.ai.orchestrator import AIOrchestrator
from app.ai.registry.prompts import PromptTemplate
from app.models.entities import User, AIRun

settings = get_settings()


async def get_or_create_test_user(session: AsyncSession) -> UUID:
    """Берём первого пользователя из БД или создаём тестового."""
    result = await session.execute(select(User).limit(1))
    user = result.scalar_one_or_none()
    if user:
        return user.id

    # Создаём тестового пользователя
    user = User(
        id=uuid4(),
        email="test-orchestrator@example.com",
        hashed_password="fake",
        full_name="Test Orchestrator",
    )
    session.add(user)
    await session.flush()
    return user.id


async def show_last_ai_run(session: AsyncSession):
    """Показывает последнюю запись в AI_RUNS."""
    from sqlalchemy import desc
    result = await session.execute(
        select(AIRun).order_by(desc(AIRun.created_at)).limit(1)
    )
    run = result.scalar_one_or_none()
    if not run:
        print("No AI_RUNS found")
        return

    print("\n" + "=" * 60)
    print("LAST AI_RUN RECORD")
    print("=" * 60)
    print(f"id:            {run.id}")
    print(f"status:        {run.status}")
    print(f"workflow:      {run.workflow_name}")
    print(f"provider:      {run.provider_name}")
    print(f"model:         {run.model_name}")
    print(f"prompt_version:{run.prompt_version}")
    print(f"duration_ms:   {run.duration_ms}")
    print(f"tokens_used:   {run.tokens_used_json}")
    if run.error_text:
        print(f"error:         {run.error_text[:200]}")
    print(f"input_len:     {len(str(run.input_snapshot_json))} chars")
    print(f"output_len:    {len(str(run.output_snapshot_json))} chars")
    print("=" * 60)


async def test_ai_orchestrator(session: AsyncSession, user_id: UUID):
    """Ручной тест: выполняет один AI-запрос и печатает результат."""

    orchestrator = AIOrchestrator.from_settings()

    # GigaChat использует self-signed cert — отключаем verify для теста
    import httpx
    orchestrator.client.client = httpx.AsyncClient(
        base_url=orchestrator.client.base_url,
        headers={"Authorization": f"Bearer {orchestrator.client.api_key}", "Content-Type": "application/json"},
        timeout=settings.ai_request_timeout,
        verify=False,
    )

    try:
        result = await orchestrator.execute(
            session,
            user_id=user_id,
            prompt_template=PromptTemplate.RESUME_ENHANCE_V1,
            prompt_vars={
                "resume_text": (
                    "Python developer with 3 years of experience. "
                    "Built REST APIs using FastAPI and Flask. "
                    "Worked with PostgreSQL and Docker. "
                    "Interested in AI and machine learning."
                ),
            },
            workflow_name="manual_test",
            target_type="resume",
            target_id=str(uuid4()),
            language="en",
        )

        print("=" * 60)
        print("ORCHESTRATOR RESULT")
        print("=" * 60)
        print(f"result: {result['result']}")
        print(f"model:  {result['model']}")
        print(f"usage:  {result['usage']}")
        print(f"cost:   {result['cost']}")
        print("=" * 60)

    except Exception as e:
        print(f"\n[!] Request failed (expected if API key invalid): {e}")
        print("    Check AI_RUNS table for error tracing record.")

    finally:
        await orchestrator.aclose()


async def main():
    if not settings.gigachat_api_key:
        print("ERROR: GIGACHAT_API_KEY not set in .env")
        return

    async with AsyncSessionLocal() as session:
        user_id = await get_or_create_test_user(session)
        print(f"Using user_id: {user_id}")
        await test_ai_orchestrator(session, user_id)
        await session.commit()
        await show_last_ai_run(session)
        print("\n[OK] Done.")


if __name__ == "__main__":
    asyncio.run(main())
