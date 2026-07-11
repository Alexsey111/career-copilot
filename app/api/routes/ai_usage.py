# app/api/routes/ai_usage.py

"""Аналитика использования и стоимости AI-запросов (ТЗ §3.4 cost accounting)."""

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_active_user
from app.db.session import get_db_session
from app.models import AIRun, User
from app.schemas.json_contracts import StrictBaseModel

router = APIRouter(prefix="/me", tags=["ai-usage"])


class WorkflowUsage(StrictBaseModel):
    workflow: str
    runs: int
    total_tokens: int
    total_cost: str


class AIUsageResponse(StrictBaseModel):
    total_runs: int
    total_tokens: int
    total_cost: str
    by_workflow: list[WorkflowUsage]


@router.get("/ai-usage", response_model=AIUsageResponse)
async def get_my_ai_usage(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> AIUsageResponse:
    runs = (
        await session.execute(
            select(AIRun).where(AIRun.user_id == current_user.id)
        )
    ).scalars().all()

    by_workflow: dict[str, dict[str, int | float]] = defaultdict(
        lambda: {"runs": 0, "tokens": 0, "cost": 0.0}
    )
    total_tokens = 0
    total_cost = 0.0

    for run in runs:
        usage = run.tokens_used_json or {}
        tokens = int(usage.get("prompt_tokens", 0)) + int(
            usage.get("completion_tokens", 0)
        )
        cost = float(run.cost) if run.cost is not None else 0.0
        bucket = by_workflow[run.workflow_name]
        bucket["runs"] += 1
        bucket["tokens"] += tokens
        bucket["cost"] += cost
        total_tokens += tokens
        total_cost += cost

    return AIUsageResponse(
        total_runs=len(runs),
        total_tokens=total_tokens,
        total_cost=f"{total_cost:.6f}",
        by_workflow=[
            WorkflowUsage(
                workflow=wf,
                runs=v["runs"],
                total_tokens=v["tokens"],
                total_cost=f"{v['cost']:.6f}",
            )
            for wf, v in sorted(by_workflow.items())
        ],
    )