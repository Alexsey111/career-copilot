# app\domain\billing.py

"""Доменные модели биллинга (Этап 4 — Billing/Stripe, ТЗ §3.5).

Чистые константы и dataclass'ы без БД-зависимостей: тарифные планы, статусы
подписки, действия квот и mapping «действие → лимит free-tier». Metering
(подсчёт usage) и enforcement живут в ``QuotaService`` (``app/services``),
персистентность — в репозиториях. Образец домена: ``app/domain/case_prep.py``.

Дизайн metering (важно для корректности):
- ``generated_output`` считается по ``DocumentVersion`` (root-версии,
  ``derived_from_id IS NULL``, ``document_kind`` ∈ ``GENERATED_OUTPUT_KINDS``),
  **НЕ** по ``AIRun`` — потому что ``generate_resume``/``generate_cover_letter``
  в production детерминированные (``use_ai_enhancement=False`` по умолчанию) и
  **не трассируют AIRun**. Счёт по AIRun всегда давал бы 0.
- ``ai_request`` считается по ``AIRun`` (реальные AI-вызовы: enhance_*,
  profile extraction, interview coaching) **с исключением**
  ``GENERATED_OUTPUT_WORKFLOWS`` — чтобы при включённом AI-усилении генерация
  документа не считалась дважды (она считается как ``generated_output``).
- ``doc_upload`` считается по ``SourceFile`` (одна строка = одна загрузка).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


# --- Тарифные планы ----------------------------------------------------------

PLAN_FREE = "free"
PLAN_PAID_MONTHLY = "paid_monthly"
PLANS: tuple[str, ...] = (PLAN_FREE, PLAN_PAID_MONTHLY)

# paid-планы не подчиняются free-tier квотам (unlimited).
UNLIMITED_PLANS: frozenset[str] = frozenset({PLAN_PAID_MONTHLY})


def plan_is_unlimited(plan: str) -> bool:
    """True для платных планов (квоты не применяются)."""
    return plan in UNLIMITED_PLANS


def is_valid_plan(plan: str) -> bool:
    return plan in PLANS


# --- Статусы подписки --------------------------------------------------------

SUBSCRIPTION_ACTIVE = "active"
SUBSCRIPTION_PAST_DUE = "past_due"
SUBSCRIPTION_CANCELED = "canceled"
SUBSCRIPTION_ENDED = "ended"
SUBSCRIPTION_STATUSES: tuple[str, ...] = (
    SUBSCRIPTION_ACTIVE,
    SUBSCRIPTION_PAST_DUE,
    SUBSCRIPTION_CANCELED,
    SUBSCRIPTION_ENDED,
)

# Статусы, при которых пользователь сохраняет доступ к платным возможностям.
ACTIVE_LIKE_STATUSES: frozenset[str] = frozenset({SUBSCRIPTION_ACTIVE, SUBSCRIPTION_PAST_DUE})


def status_grants_paid_access(status: str) -> bool:
    """``active``/``past_due`` → доступ к платным возможностям; ``canceled``/
    ``ended`` → нет (льготный период не моделируется отдельно)."""
    return status in ACTIVE_LIKE_STATUSES


# --- Действия квот -----------------------------------------------------------

QUOTA_AI_REQUEST = "ai_request"
QUOTA_DOC_UPLOAD = "doc_upload"
QUOTA_GENERATED_OUTPUT = "generated_output"
# Demo-режим: лимит на запуск **анализа** вакансии в коротком скользящем
# окне (час). Слот списывается когда создан ``VacancyAnalysis`` (то есть
# когда AI реально потратился), а НЕ на сам импорт — вставка/правка
# текста бесплатна, можно править сколько угодно. См. ``app/core/config.py``
# ``billing_free_tier_vacancy_imports_limit`` и
# ``demo_vacancy_import_window_seconds``. Окно — секунды (см.
# ``QuotaService._window_start_for``). Считаем по ``vacancy_analyses`` JOIN
# ``vacancies`` по user_id.
QUOTA_VACANCY_IMPORT = "vacancy_import"
QUOTA_ACTIONS: tuple[str, ...] = (
    QUOTA_AI_REQUEST,
    QUOTA_DOC_UPLOAD,
    QUOTA_GENERATED_OUTPUT,
    QUOTA_VACANCY_IMPORT,
)


def is_valid_quota_action(action: str) -> bool:
    return action in QUOTA_ACTIONS


# AI workflow_name, которые производят сгенерированный документ (resume/cover
# letter). При включённом AI-усилении эти AIRun исключаются из подсчёта
# ``ai_request`` (считаются отдельно как ``generated_output``).
GENERATED_OUTPUT_WORKFLOWS: frozenset[str] = frozenset(
    {
        "resume_tailoring",
        "cover_letter_enhance",
    }
)

# document_kind DocumentVersion, считающиеся сгенерированным output'ом
# (root-версии, не enhancement-производные).
GENERATED_OUTPUT_KINDS: frozenset[str] = frozenset({"resume", "cover_letter"})

# Mapping «действие квоты → имя поля Settings с free-tier лимитом».
FREE_TIER_LIMIT_ATTR: dict[str, str] = {
    QUOTA_AI_REQUEST: "billing_free_tier_ai_requests_limit",
    QUOTA_DOC_UPLOAD: "billing_free_tier_doc_uploads_limit",
    QUOTA_GENERATED_OUTPUT: "billing_free_tier_generated_outputs_limit",
    QUOTA_VACANCY_IMPORT: "billing_free_tier_vacancy_imports_limit",
}

# Действия с секундным (а не дневным) скользящим окном → имя поля Settings с
# длительностью окна в секундах. На данный момент только demo-лимит импорта
# вакансий (час); остальные используют ``billing_quota_window_days``.
QUOTA_WINDOW_SECONDS_ATTR: dict[str, str] = {
    QUOTA_VACANCY_IMPORT: "demo_vacancy_import_window_seconds",
}


def free_tier_limit(settings: Any, action: str) -> int:
    """Возвращает free-tier лимит для действия из Settings. ``settings`` —
    экземпляр ``app.core.config.Settings``."""
    attr = FREE_TIER_LIMIT_ATTR.get(action)
    if attr is None:
        raise ValueError(f"unknown quota action: {action!r}")
    return int(getattr(settings, attr))


# --- Решение по квоте --------------------------------------------------------


@dataclass(slots=True)
class QuotaDecision:
    """Результат проверки квоты перед выполнением действия.

    ``allowed=False`` → эндпоинт возвращает 402 с ``detail`` = ``reason``
    (см. ``require_quota`` в ``app/api/dependencies``).
    """

    allowed: bool
    action: str
    plan: str
    used: int
    limit: int | None  # None = unlimited (платный план)
    reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)