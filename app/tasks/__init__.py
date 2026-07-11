# app/tasks/__init__.py

from app.celery_app import celery_app

__all__ = ["celery_app"]
