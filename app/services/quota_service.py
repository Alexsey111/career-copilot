# app\services\quota_service.py

"""Сервис квот биллинга (Этап 4 — Billing, ТЗ §3.5).

Metering (подсчёт usage в скользящем окне) и enforcement (проверка перед
действием → ``QuotaDecision``). Free-tier: жёсткий enforcement, превышение →
402 (через ``require_quota`` в ``app/api/dependencies``). paid_monthly =
unlimited (квоты не применяются при активной подписке).

Metering-источники (см. обоснование в ``app/domain/billing.py``):
- ``ai_request`` → ``AIRun`` (исключая ``GENERATED_OUTPUT_WORKFLOWS``).
- ``doc_upload`` → ``SourceFile``.
- ``generated_output`` → ``DocumentVersion`` (root-версии,
  ``derived_from_id IS NULL``, ``document_kind`` ∈ ``GENERATED_OUTPUT_KINDS``).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.domain.billing import (
    GENERATED_OUTPUT_KINDS,
    GENERATED_OUTPUT_WORKFLOWS,
    PLAN_FREE,
    QUOTA_AI_REQUEST,
    QUOTA_DOC_UPLOAD,
    QUOTA_GENERATED_OUTPUT,
    QUOTA_VACANCY_IMPORT,
    QUOTA_WINDOW_SECONDS_ATTR,
    QuotaDecision,
    free_tier_limit,
    plan_is_unlimited,
    status_grants_paid_access,
)
from app.models import AIRun, DocumentVersion, SourceFile, Vacancy
from app.repositories.subscription_repository import SubscriptionRepository


class QuotaService:
    """Подсчёт usage и проверка квот."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        subscription_repository: SubscriptionRepository | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._subscription_repository = subscription_repository or SubscriptionRepository()

    async def get_subscription_view(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
    ) -> tuple[str, str]:
        """Возвращает ``(plan, status)``. Пользователь без записи →
        ``(free, active)`` (in-memory view)."""
        subscription = await self._subscription_repository.get_or_none(
            session, user_id=user_id
        )
        if subscription is None:
            return PLAN_FREE, "active"
        return subscription.plan, subscription.status

    def _window_start(self) -> datetime:
        days = self._settings.billing_quota_window_days
        return datetime.now(timezone.utc) - timedelta(days=days)

    def _window_start_for(self, action: str) -> datetime:
        """Скользящее окно для действия. Действия из ``QUOTA_WINDOW_SECONDS_ATTR``
        (demo-лимит импорта вакансий) используют секундное окно; остальные —
        ``billing_quota_window_days``.
        """
        seconds_attr = QUOTA_WINDOW_SECONDS_ATTR.get(action)
        if seconds_attr is not None:
            seconds = int(getattr(self._settings, seconds_attr))
            return datetime.now(timezone.utc) - timedelta(seconds=seconds)
        return self._window_start()

    async def count_usage(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        action: str,
    ) -> int:
        """Считает usage действия в скользящем окне.

        ``vacancy_import`` — секунды (``demo_vacancy_import_window_seconds``);
        остальные — дни (``billing_quota_window_days``).
        """
        window_start = self._window_start_for(action)

        if action == QUOTA_AI_REQUEST:
            stmt = (
                select(func.count())
                .select_from(AIRun)
                .where(AIRun.user_id == user_id)
                .where(AIRun.created_at >= window_start)
                .where(AIRun.workflow_name.not_in(GENERATED_OUTPUT_WORKFLOWS))
            )
        elif action == QUOTA_DOC_UPLOAD:
            stmt = (
                select(func.count())
                .select_from(SourceFile)
                .where(SourceFile.user_id == user_id)
                .where(SourceFile.created_at >= window_start)
            )
        elif action == QUOTA_GENERATED_OUTPUT:
            stmt = (
                select(func.count())
                .select_from(DocumentVersion)
                .where(DocumentVersion.user_id == user_id)
                .where(DocumentVersion.created_at >= window_start)
                .where(DocumentVersion.derived_from_id.is_(None))
                .where(DocumentVersion.document_kind.in_(GENERATED_OUTPUT_KINDS))
            )
        elif action == QUOTA_VACANCY_IMPORT:
            stmt = (
                select(func.count())
                .select_from(Vacancy)
                .where(Vacancy.user_id == user_id)
                .where(Vacancy.created_at >= window_start)
            )
        else:
            raise ValueError(f"unknown quota action: {action!r}")

        result = await session.execute(stmt)
        return int(result.scalar_one())

    async def check_quota(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        action: str,
    ) -> QuotaDecision:
        """Проверяет квоту перед выполнением действия.

        paid_monthly с активным статусом → unlimited (``limit=None``).
        Иначе free-tier: ``allowed = used < limit``.
        """
        plan, status = await self.get_subscription_view(session, user_id=user_id)

        if plan_is_unlimited(plan) and status_grants_paid_access(status):
            used = await self.count_usage(session, user_id=user_id, action=action)
            return QuotaDecision(
                allowed=True,
                action=action,
                plan=plan,
                used=used,
                limit=None,
                reason=None,
            )

        limit = free_tier_limit(self._settings, action)
        used = await self.count_usage(session, user_id=user_id, action=action)
        allowed = used < limit
        reason = None if allowed else (
            f"free-tier quota exceeded for '{action}': used {used} of {limit}"
        )
        return QuotaDecision(
            allowed=allowed,
            action=action,
            plan=plan,
            used=used,
            limit=limit,
            reason=reason,
        )

    async def get_usage(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
    ) -> dict[str, Any]:
        """Текущее usage по всем действиям (для ``/me/billing/subscription``).

        ``vacancy_import`` использует секундное окно (``window_seconds``),
        остальные — дневное (``window_days``).
        """
        plan, status = await self.get_subscription_view(session, user_id=user_id)
        unlimited = plan_is_unlimited(plan) and status_grants_paid_access(status)
        usage: dict[str, Any] = {}
        for action in (
            QUOTA_AI_REQUEST,
            QUOTA_DOC_UPLOAD,
            QUOTA_GENERATED_OUTPUT,
            QUOTA_VACANCY_IMPORT,
        ):
            used = await self.count_usage(session, user_id=user_id, action=action)
            entry: dict[str, Any] = {
                "used": used,
                "limit": None if unlimited else free_tier_limit(self._settings, action),
            }
            seconds_attr = QUOTA_WINDOW_SECONDS_ATTR.get(action)
            if seconds_attr is not None:
                entry["window_seconds"] = int(getattr(self._settings, seconds_attr))
            else:
                entry["window_days"] = self._settings.billing_quota_window_days
            usage[action] = entry
        return usage