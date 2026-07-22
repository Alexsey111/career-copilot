# app/tasks/notification_tasks.py

"""Celery-таски proactive Telegram-уведомлений (Этап 5, ТЗ §3.6).

Beat-таска ``dispatch_telegram_alerts`` (раз в час, очередь ``notification``)
вызывает ``TelegramDispatchService.dispatch_pending_alerts``. Паттерн
sync ``def`` + ``asyncio.get_event_loop().run_until_complete`` +
``AsyncSessionLocal`` (НЕ sync engine) — образец
``app/tasks/pipeline_tasks.py``.
"""

from __future__ import annotations

import logging

from app.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.notification_tasks.dispatch_telegram_alerts")
def dispatch_telegram_alerts() -> dict:
    import asyncio

    from app.db.session import AsyncSessionLocal
    from app.services.telegram_dispatch_service import TelegramDispatchService

    async def _run():
        async with AsyncSessionLocal() as session:
            service = TelegramDispatchService()
            return await service.dispatch_pending_alerts(session)

    return asyncio.get_event_loop().run_until_complete(_run())