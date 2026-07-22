# tests/test_telegram_dispatch.py

"""Тесты proactive dispatch (Этап 5) — прямой вызов сервиса со стабами.

Celery-таска ``dispatch_telegram_alerts`` — тонкая обёртка (тестируется smoke),
бизнес-логика (дедуп, фильтр, error handling) проверяется через прямой вызов
``TelegramDispatchService.dispatch_pending_alerts``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.models import TelegramDispatchLog, User
from app.repositories.telegram_dispatch_log_repository import (
    TelegramDispatchLogRepository,
)
from app.services.telegram_dispatch_service import TelegramDispatchService
from factories.fake_telegram import FakeTelegramClient, telegram_api_error


def _reminder(application_id, *, reminder_type="draft_stale", days=20):
    return SimpleNamespace(
        application_id=application_id,
        reminder_type=reminder_type,
        title="Черновик без активности",
        description=f"Отклик в черновике {days} дн.",
        days_since_event=days,
        created_at=datetime.now(timezone.utc),
    )


class _UserRepo:
    def __init__(self, subscribers):
        self._subscribers = subscribers

    async def list_telegram_subscribers(self, session):
        return self._subscribers


class _ReminderService:
    def __init__(self, reminders_by_user):
        self._reminders = reminders_by_user

    async def get_reminders(self, session, *, user_id):
        return self._reminders.get(user_id, [])


def _service(subscribers, reminders_by_user, fake):
    return TelegramDispatchService(
        user_repo=_UserRepo(subscribers),
        reminder_service=_ReminderService(reminders_by_user),
        dispatch_log_repo=TelegramDispatchLogRepository(),
        telegram_client=fake,
    )


@pytest.mark.asyncio
async def test_dispatch_sends_and_logs(db_session, test_user):
    test_user.telegram_chat_id = "111"
    test_user.telegram_dispatch_enabled = True
    await db_session.flush()

    app_id = uuid4()
    fake = FakeTelegramClient()
    svc = _service([test_user], {test_user.id: [_reminder(app_id)]}, fake)

    result = await svc.dispatch_pending_alerts(db_session)

    assert result["subscribers"] == 1
    assert result["dispatched"] == 1
    assert result["skipped"] == 0
    assert result["errors"] == 0
    assert len(fake.send_message_calls) == 1
    logs = (
        await db_session.execute(
            TelegramDispatchLog.__table__.select()  # type: ignore[attr-defined]
        )
    ).all()
    assert len(logs) == 1


@pytest.mark.asyncio
async def test_dispatch_dedup_skips_second_run(db_session, test_user):
    test_user.telegram_chat_id = "222"
    test_user.telegram_dispatch_enabled = True
    await db_session.flush()

    app_id = uuid4()
    reminders = [_reminder(app_id)]
    fake = FakeTelegramClient()
    svc = _service([test_user], {test_user.id: reminders}, fake)

    first = await svc.dispatch_pending_alerts(db_session)
    assert first["dispatched"] == 1

    # Второй запуск того же дня — дедуп через dispatch_log.exists.
    second = await svc.dispatch_pending_alerts(db_session)
    assert second["dispatched"] == 0
    assert second["skipped"] == 1
    assert len(fake.send_message_calls) == 1  # не дублировали отправку


@pytest.mark.asyncio
async def test_dispatch_no_reminders_noop(db_session, test_user):
    test_user.telegram_chat_id = "333"
    test_user.telegram_dispatch_enabled = True
    await db_session.flush()

    fake = FakeTelegramClient()
    svc = _service([test_user], {test_user.id: []}, fake)
    result = await svc.dispatch_pending_alerts(db_session)
    assert result["dispatched"] == 0
    assert result["skipped"] == 0
    assert fake.send_message_calls == []


@pytest.mark.asyncio
async def test_dispatch_skips_user_without_chat_id(db_session, test_user):
    # list_telegram_subscribers фильтрует по chat_id, но проверим что даже
    # если подписчик без chat_id попал — send не падает. Репо возвращает
    # user без chat_id (гипотетический bypass фильтра).
    test_user.telegram_dispatch_enabled = True
    test_user.telegram_chat_id = None
    await db_session.flush()

    fake = FakeTelegramClient()
    svc = _service([test_user], {test_user.id: [_reminder(uuid4())]}, fake)
    # send_message на chat_id=None → FakeTelegramClient append (str(None)).
    # Реальный TelegramClient упал бы 400; здесь просто проверяем, что
    # dispatch не падает и логирует результат.
    result = await svc.dispatch_pending_alerts(db_session)
    assert result["subscribers"] == 1


@pytest.mark.asyncio
async def test_dispatch_send_error_does_not_log(db_session, test_user):
    test_user.telegram_chat_id = "444"
    test_user.telegram_dispatch_enabled = True
    await db_session.flush()

    app_id = uuid4()
    fake = FakeTelegramClient()
    fake.send_error = telegram_api_error(400, "chat not found")
    svc = _service([test_user], {test_user.id: [_reminder(app_id)]}, fake)

    result = await svc.dispatch_pending_alerts(db_session)
    assert result["dispatched"] == 0
    assert result["errors"] == 1
    # Лог не создаётся при ошибке отправки.
    logs = (
        await db_session.execute(TelegramDispatchLog.__table__.select())  # type: ignore[attr-defined]
    ).all()
    assert len(logs) == 0


@pytest.mark.asyncio
async def test_dispatch_multiple_users_independent(db_session):
    u1 = User(email="u1-disp@local.test", auth_provider="test")
    u2 = User(email="u2-disp@local.test", auth_provider="test")
    db_session.add_all([u1, u2])
    u1.telegram_chat_id = "555"
    u1.telegram_dispatch_enabled = True
    u2.telegram_chat_id = "666"
    u2.telegram_dispatch_enabled = True
    await db_session.flush()

    # u2 получит ошибку отправки → не должен ронять обработку u1 (хотя порядок
    # один, проверим независимость: оба обрабатываются, но u2 error).
    fake = FakeTelegramClient()
    # Эмулируем ошибку только для chat_id 666.
    original_send = fake.send_message

    async def selective_send(chat_id, text, *, parse_mode=None):
        if str(chat_id) == "666":
            raise telegram_api_error(400, "blocked")
        return await original_send(chat_id, text, parse_mode=parse_mode)

    fake.send_message = selective_send  # type: ignore[assignment]

    reminders = {
        u1.id: [_reminder(uuid4())],
        u2.id: [_reminder(uuid4())],
    }
    svc = _service([u1, u2], reminders, fake)
    result = await svc.dispatch_pending_alerts(db_session)
    assert result["dispatched"] == 1
    assert result["errors"] == 1
    assert len(fake.send_message_calls) == 1  # только u1