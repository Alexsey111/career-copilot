"""
Намеренное ломание оркестратора для проверки error handling и tracing.

Сценарии:
1. Невалидный API key → HTTP 401 → status=failed
2. Timeout 0.01s → asyncio.TimeoutError → status=failed

Запуск:
    cd "d:/python projects/career-copilot"
    python -m scripts.test_orchestrator_break
"""

from __future__ import annotations

import asyncio
import httpx
from uuid import uuid4

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.core.config import get_settings
from app.ai.orchestrator import AIOrchestrator
from app.ai.config import AIOrchestratorConfig
from app.ai.registry.prompts import PromptTemplate
from app.models.entities import User, AIRun

settings = get_settings()


async def get_test_user(session: AsyncSession) -> User:
    result = await session.execute(select(User).limit(1))
    user = result.scalar_one_or_none()
    if user:
        return user

    user = User(
        id=uuid4(),
        email="test-break@example.com",
        hashed_password="fake",
        full_name="Test Break",
    )
    session.add(user)
    await session.flush()
    return user


def create_fake_gigachat_client():
    """Создаёт GigaChatClient с фейковым ключом (обходим __init__ проверку)."""
    from app.ai.clients.gigachat import GigaChatClient

    client = GigaChatClient.__new__(GigaChatClient)
    client.base_url = settings.gigachat_base_url or "https://gigachat.devices.sberbank.ru/api/v1"
    client.api_key = "fake-invalid-key-for-testing"
    client.client = httpx.AsyncClient(
        base_url=client.base_url,
        headers={
            "Authorization": f"Bearer {client.api_key}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
        verify=False,
    )
    return client


async def test_invalid_api_key(session: AsyncSession, user: User):
    """Сценарий 1: невалидный API key → 401 Unauthorized."""
    print("\n[TEST 1] Invalid API key -> expect 401")
    print("-" * 60)

    client = create_fake_gigachat_client()
    orchestrator = AIOrchestrator(
        client=client,
        config=AIOrchestratorConfig(
            default_model="gigachat-pro",
            enable_tracing=True,
            max_retries=1,
            retry_backoff_sec=0.1,
        ),
    )

    try:
        await orchestrator.execute(
            session,
            user_id=user.id,
            prompt_template=PromptTemplate.RESUME_ENHANCE_V1,
            prompt_vars={"resume_text": "Python developer", "language": "en"},
            workflow_name="break_test_invalid_key",
            target_type="resume",
            target_id=str(uuid4()),
        )
        print("FAIL: expected exception, got success")
    except Exception as e:
        print(f"OK: Caught expected error: {type(e).__name__}")
    finally:
        await orchestrator.aclose()


async def test_timeout(session: AsyncSession, user: User):
    """Сценарий 2: timeout 0.01s → asyncio.TimeoutError."""
    print("\n[TEST 2] Timeout 0.01s -> expect TimeoutError")
    print("-" * 60)

    client = create_fake_gigachat_client()
    orchestrator = AIOrchestrator(
        client=client,
        config=AIOrchestratorConfig(
            default_model="gigachat-pro",
            enable_tracing=True,
            request_timeout_sec=0.01,
            max_retries=0,
        ),
    )

    try:
        await orchestrator.execute(
            session,
            user_id=user.id,
            prompt_template=PromptTemplate.RESUME_ENHANCE_V1,
            prompt_vars={"resume_text": "Python developer", "language": "en"},
            workflow_name="break_test_timeout",
            target_type="resume",
            target_id=str(uuid4()),
        )
        print("FAIL: expected exception, got success")
    except Exception as e:
        print(f"OK: Caught expected error: {type(e).__name__}")
    finally:
        await orchestrator.aclose()


async def show_break_results(session: AsyncSession):
    """Показывает последние записи break_test* в AI_RUNS."""
    from sqlalchemy import func

    result = await session.execute(
        select(AIRun)
        .where(AIRun.workflow_name.like("break_test_%"))
        .order_by(desc(AIRun.created_at))
        .limit(5)
    )
    rows = result.scalars().all()

    print("\n" + "=" * 80)
    print("BREAK TEST RESULTS IN AI_RUNS")
    print("=" * 80)
    print(f"{'status':<10} | {'duration_ms':>8} | {'error_snippet':<45}")
    print("-" * 80)

    for r in rows:
        error_snippet = (r.error_text or "")[:45] if r.error_text else "<no error>"
        print(f"{r.status:<10} | {r.duration_ms:>8} | {error_snippet}")

    # Assertions
    failed_rows = [r for r in rows if r.status == "failed"]
    assert len(failed_rows) >= 2, f"Expected >= 2 failed rows, got {len(failed_rows)}"

    invalid_key_row = next((r for r in rows if r.workflow_name == "break_test_invalid_key"), None)
    timeout_row = next((r for r in rows if r.workflow_name == "break_test_timeout"), None)

    assert invalid_key_row is not None, "Missing break_test_invalid_key row"
    assert invalid_key_row.status == "failed", f"Expected failed, got {invalid_key_row.status}"
    assert invalid_key_row.error_text is not None, "error_text should be filled"
    assert "401" in invalid_key_row.error_text or "Unauthorized" in invalid_key_row.error_text, \
        f"Expected 401 in error_text, got: {invalid_key_row.error_text}"

    assert timeout_row is not None, "Missing break_test_timeout row"
    assert timeout_row.status == "failed", f"Expected failed, got {timeout_row.status}"
    assert timeout_row.error_text is not None, "error_text should be filled"
    assert "timeout" in timeout_row.error_text.lower(), \
        f"Expected timeout in error_text, got: {timeout_row.error_text}"

    print("-" * 80)
    print("ALL ASSERTIONS PASSED")
    print("=" * 80)


async def main():
    async with AsyncSessionLocal() as session:
        user = await get_test_user(session)
        print(f"Using user: {user.id}")

        await test_invalid_api_key(session, user)
        await test_timeout(session, user)

        await session.commit()
        await show_break_results(session)
        print("\n[OK] Break test complete.")


if __name__ == "__main__":
    asyncio.run(main())
