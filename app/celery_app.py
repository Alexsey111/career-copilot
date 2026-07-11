# app/celery_app.py

from __future__ import annotations

import logging
from celery import Celery
from celery.signals import task_prerun, task_postrun

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

celery_app = Celery(
    "career_copilot",
    broker=f"redis://{settings.redis_host}:{settings.redis_port}/0",
    backend=f"redis://{settings.redis_host}:{settings.redis_port}/1",
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=300,
    task_time_limit=600,
    task_default_queue="career_copilot",
    task_routes={
        "app.tasks.vacancy_tasks.*": {"queue": "vacancy"},
        "app.tasks.resume_tasks.*": {"queue": "resume"},
        "app.tasks.cover_letter_tasks.*": {"queue": "cover_letter"},
        "app.tasks.interview_tasks.*": {"queue": "interview"},
        "app.tasks.pipeline_tasks.*": {"queue": "pipeline"},
    },
    beat_schedule={
        "cleanup-stale-executions": {
            "task": "app.tasks.pipeline_tasks.cleanup_stale_executions",
            "schedule": 300.0,
        },
    },
)

celery_app.autodiscover_tasks(["app.tasks"])


@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, **kwargs):
    from app.core.tracing import set_trace_context
    set_trace_context(trace_id=task_id, correlation_id=task_id)


@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, **kwargs):
    from app.core.tracing import clear_trace_context
    clear_trace_context()
