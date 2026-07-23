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
from app.models import AIRun, DocumentVersion, SourceFile, Vacancy, VacancyAnalysis
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
        return await self._count_stmt(session, user_id=user_id, action=action, window_start=window_start)

    async def count_usage_with_oldest(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        action: str,
    ) -> tuple[int, datetime | None]:
        """Считает usage + возвращает timestamp самой старой записи в окне.

        Самая старая запись — это та, что «выйдет» из окна следующей, поэтому
        фронт использует её для обратного отсчёта «сброс через X мин».
        Если used=0, возвращает (0, None).
        """
        window_start = self._window_start_for(action)
        count = await self._count_stmt(
            session, user_id=user_id, action=action, window_start=window_start
        )
        if count == 0:
            return 0, None
        oldest = await self._oldest_stmt(
            session, user_id=user_id, action=action, window_start=window_start
        )
        return count, oldest

    async def _count_stmt(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        action: str,
        window_start: datetime,
    ) -> int:
        stmt = self._build_window_stmt(action, user_id=user_id, window_start=window_start)
        result = await session.execute(stmt)
        return int(result.scalar_one())

    async def _oldest_stmt(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        action: str,
        window_start: datetime,
    ) -> datetime | None:
        # Берём те же фильтры что и для count, но aggregate MIN(created_at).
        # Для ``vacancy_import`` — отдельный путь: VacancyAnalysis JOIN Vacancy
        # (у VacancyAnalysis нет user_id — он лежит на родительской Vacancy).
        if action == QUOTA_VACANCY_IMPORT:
            stmt = (
                select(func.min(VacancyAnalysis.created_at))
                .join(Vacancy, Vacancy.id == VacancyAnalysis.vacancy_id)
                .where(Vacancy.user_id == user_id)
                .where(VacancyAnalysis.created_at >= window_start)
            )
            result = await session.execute(stmt)
            value = result.scalar_one_or_none()
            return value if value is None else value

        model = self._model_for_action(action)
        stmt = (
            select(func.min(model.created_at))
            .where(model.user_id == user_id)
            .where(model.created_at >= window_start)
        )
        if action == QUOTA_AI_REQUEST:
            stmt = stmt.where(model.workflow_name.not_in(GENERATED_OUTPUT_WORKFLOWS))
        elif action == QUOTA_GENERATED_OUTPUT:
            stmt = (
                stmt.where(model.derived_from_id.is_(None))
                .where(model.document_kind.in_(GENERATED_OUTPUT_KINDS))
            )
        result = await session.execute(stmt)
        value = result.scalar_one_or_none()
        return value if value is None else value

    def _model_for_action(self, action: str):
        if action == QUOTA_AI_REQUEST:
            return AIRun
        if action == QUOTA_DOC_UPLOAD:
            return SourceFile
        if action == QUOTA_GENERATED_OUTPUT:
            return DocumentVersion
        if action == QUOTA_VACANCY_IMPORT:
            # Слот «импорта» теперь = запуск анализа (VacancyAnalysis JOIN
            # Vacancy по user_id). Импорт самой вакансии — бесплатный.
            return VacancyAnalysis
        raise ValueError(f"unknown quota action: {action!r}")

    def _build_window_stmt(self, action: str, *, user_id: UUID, window_start: datetime):
        if action == QUOTA_AI_REQUEST:
            return (
                select(func.count())
                .select_from(AIRun)
                .where(AIRun.user_id == user_id)
                .where(AIRun.created_at >= window_start)
                .where(AIRun.workflow_name.not_in(GENERATED_OUTPUT_WORKFLOWS))
            )
        if action == QUOTA_DOC_UPLOAD:
            return (
                select(func.count())
                .select_from(SourceFile)
                .where(SourceFile.user_id == user_id)
                .where(SourceFile.created_at >= window_start)
            )
        if action == QUOTA_GENERATED_OUTPUT:
            return (
                select(func.count())
                .select_from(DocumentVersion)
                .where(DocumentVersion.user_id == user_id)
                .where(DocumentVersion.created_at >= window_start)
                .where(DocumentVersion.derived_from_id.is_(None))
                .where(DocumentVersion.document_kind.in_(GENERATED_OUTPUT_KINDS))
            )
        if action == QUOTA_VACANCY_IMPORT:
            # Считаем анализы (VacancyAnalysis), отфильтрованные по владельцу
            # вакансии (JOIN Vacancy). created_at берём с VacancyAnalysis —
            # это момент запуска анализа.
            return (
                select(func.count())
                .select_from(VacancyAnalysis)
                .join(Vacancy, Vacancy.id == VacancyAnalysis.vacancy_id)
                .where(Vacancy.user_id == user_id)
                .where(VacancyAnalysis.created_at >= window_start)
            )
        raise ValueError(f"unknown quota action: {action!r}")

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
            used, oldest = await self.count_usage_with_oldest(
                session, user_id=user_id, action=action
            )
            entry: dict[str, Any] = {
                "used": used,
                "limit": None if unlimited else free_tier_limit(self._settings, action),
            }
            seconds_attr = QUOTA_WINDOW_SECONDS_ATTR.get(action)
            if seconds_attr is not None:
                entry["window_seconds"] = int(getattr(self._settings, seconds_attr))
            else:
                entry["window_days"] = self._settings.billing_quota_window_days
            entry["oldest_in_window"] = oldest
            usage[action] = entry
        return usage