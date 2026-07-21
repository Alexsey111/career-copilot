# app\services\stripe_client.py

"""Тонкая обёртка над официальным Stripe SDK (Этап 4 — Billing).

Изоляция Stripe-вызовов в одном классе, чтобы ``BillingService`` зависел от
абстракции, а не от глобального состояния ``stripe``. В тестах подменяется
фактической реализацией (fake), возвращающей plain-dict'ы — без реальных
Stripe-ключей и сетевых вызовов (выбор пользователя: полностью mock в тестах).

Все методы возвращают plain-dict'ы с полями, нужными сервису, — это развязывает
сервис с объектной моделью Stripe и упрощает стаб-моки. ``construct_webhook_event``
возвращает dict-like StripeObject (поддерживает ``["type"]`` / ``["data"]``);
в тестах fake возвращает обычный dict.
"""

from __future__ import annotations

from typing import Any

import stripe

from app.core.config import Settings, get_settings


class StripeClient:
    """DI-mockable обёртка Stripe SDK."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        if self._settings.stripe_secret_key:
            stripe.api_key = self._settings.stripe_secret_key

    def construct_webhook_event(
        self,
        *,
        payload: bytes | str,
        sig_header: str,
    ) -> Any:
        """Проверяет подпись Stripe и возвращает Event (dict-like).

        Raises ``stripe.error.SignatureVerificationError`` при невалидной
        подписи — эндпоинт webhook'а мапит это в 400.
        """
        return stripe.Webhook.construct_event(
            payload,
            sig_header,
            self._settings.stripe_webhook_secret,
            tolerance=self._settings.stripe_webhook_tolerance,
        )

    def create_checkout_session(
        self,
        *,
        customer_email: str,
        client_reference_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
    ) -> dict[str, Any]:
        """Создаёт Stripe Checkout Session (subscription mode)."""
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            customer_email=customer_email,
            client_reference_id=client_reference_id,
            success_url=success_url,
            cancel_url=cancel_url,
        )
        return {
            "id": session.id,
            "url": session.url,
            "customer": session.customer,
            "subscription": session.subscription,
        }

    def create_billing_portal_session(
        self,
        *,
        customer_id: str,
        return_url: str,
    ) -> dict[str, Any]:
        """Создаёт Stripe Billing Portal Session (управление подпиской)."""
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )
        return {"url": session.url}

    def retrieve_subscription(self, subscription_id: str) -> dict[str, Any]:
        """Возвращает ключевые поля подписки (для webhook-обработки)."""
        sub = stripe.Subscription.retrieve(subscription_id)
        return {
            "id": sub.id,
            "status": sub.status,
            "customer": sub.customer,
            "current_period_end": sub.current_period_end,
        }