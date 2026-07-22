# app/repositories/telegram_dispatch_log_repository.py

"""Репозиторий дедуп-лога proactive Telegram-уведомлений (Этап 5, ТЗ §3.6).

``dispatch_key`` = ``{reminder_type}:{application_id}:{YYYY-MM-DD}`` →
максимум 1 уведомление типа на application в день (UTC). UniqueConstraint на
БД (``uq_telegram_dispatch_log_user_key``) — second слой защиты от Celery-beat
гонок; репозиторийный ``exists`` — первый слой (чтобы не плодить rollback'и).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TelegramDispatchLog


class TelegramDispatchLogRepository:
    async def exists(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        dispatch_key: str,
    ) -> bool:
        stmt = select(TelegramDispatchLog.id).where(
            TelegramDispatchLog.user_id == user_id,
            TelegramDispatchLog.dispatch_key == dispatch_key,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def create(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        dispatch_key: str,
        dispatch_type: str,
        payload_hash: str | None = None,
    ) -> TelegramDispatchLog | None:
        """Создаёт запись лога. Возвращает None при дедуп-конфликте (гонка) —
        caller воспринимает как «уже отправлено», без ронятия батча. Конфликт
        изолируется savepoint'ом, чтобы не инвалидировать внешнюю транзакцию.
        """
        log = TelegramDispatchLog(
            user_id=user_id,
            dispatch_key=dispatch_key,
            dispatch_type=dispatch_type,
            payload_hash=payload_hash,
        )
        try:
            async with session.begin_nested():
                session.add(log)
                await session.flush()
        except IntegrityError:
            # savepoint откатан; внешняя транзакция жива — лог не персистится.
            return None
        await session.refresh(log)
        return log