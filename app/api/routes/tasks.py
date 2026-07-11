# app/api/routes/tasks.py

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import Field

from app.api.dependencies import get_current_active_user
from app.models import User
from app.schemas.json_contracts import StrictBaseModel

router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskSubmitRequest(StrictBaseModel):
    task_name: str
    kwargs: dict = Field(default_factory=dict)


class TaskStatusResponse(StrictBaseModel):
    task_id: str
    status: str
    result: dict | None = None
    error: str | None = None


@router.post("/submit", response_model=TaskStatusResponse)
async def submit_task(
    payload: TaskSubmitRequest,
    current_user: User = Depends(get_current_active_user),
) -> TaskStatusResponse:
    from app.celery_app import celery_app

    task_map = {
        "analyze_vacancy": "app.tasks.vacancy_tasks.analyze_vacancy",
        "import_and_analyze_vacancy": "app.tasks.vacancy_tasks.import_and_analyze_vacancy",
        "generate_resume": "app.tasks.resume_tasks.generate_resume",
        "generate_cover_letter": "app.tasks.cover_letter_tasks.generate_cover_letter",
        "create_interview_prep": "app.tasks.interview_tasks.create_interview_prep",
        "run_pipeline": "app.tasks.pipeline_tasks.run_pipeline",
    }

    task_name = task_map.get(payload.task_name)
    if task_name is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown task: {payload.task_name}. Available: {list(task_map.keys())}",
        )

    kwargs = {**payload.kwargs, "user_id": str(current_user.id)}

    result = celery_app.send_task(task_name, kwargs=kwargs)

    return TaskStatusResponse(
        task_id=result.id,
        status="submitted",
    )


@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_active_user),
) -> TaskStatusResponse:
    from app.celery_app import celery_app

    result = celery_app.AsyncResult(task_id)

    status_map = {
        "PENDING": "pending",
        "STARTED": "running",
        "SUCCESS": "completed",
        "FAILURE": "failed",
        "RETRY": "retrying",
        "REVOKED": "cancelled",
    }

    response_status = status_map.get(result.state, "unknown")

    return TaskStatusResponse(
        task_id=task_id,
        status=response_status,
        result=result.result if result.state == "SUCCESS" else None,
        error=str(result.info) if result.state == "FAILURE" else None,
    )


@router.delete("/{task_id}")
async def cancel_task(
    task_id: str,
    current_user: User = Depends(get_current_active_user),
) -> dict:
    from app.celery_app import celery_app

    celery_app.control.revoke(task_id, terminate=True)
    return {"status": "cancelled", "task_id": task_id}
