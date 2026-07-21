# tests\factories\fake_stripe.py

"""FakeStripeClient для тестов биллинга (Этап 4). Полностью mock — без реальных
Stripe-ключей и сети (выбор пользователя). Реализует тот же интерфейс, что
``app.services.stripe_client.StripeClient``, и возвращает plain-dict'ы.

``construct_webhook_event`` парсит JSON-payload (тесты шлют raw JSON в
``/webhooks/stripe``), игнорируя подпись — в отличие от реального StripeClient,
который verify'ит через ``stripe.Webhook.construct_event``.
"""

from __future__ import annotations

import json
from typing import Any


class FakeStripeClient:
    def __init__(self) -> None:
        self.checkout_calls: list[dict] = []
        self.portal_calls: list[dict] = []
        self.retrieve_calls: list[str] = []
        # Настраиваемые ответы (для webhook-тестов с retrieve_subscription).
        self.subscriptions: dict[str, dict[str, Any]] = {}
        # Управление ошибками.
        self.construct_error: Exception | None = None

    def construct_webhook_event(
        self,
        *,
        payload: bytes | str,
        sig_header: str,
    ) -> Any:
        if self.construct_error is not None:
            raise self.construct_error
        if isinstance(payload, (bytes, bytearray)):
            payload = payload.decode("utf-8")
        return json.loads(payload)

    def create_checkout_session(
        self,
        *,
        customer_email: str,
        client_reference_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
    ) -> dict[str, Any]:
        n = len(self.checkout_calls)
        sid = f"cs_test_{n}"
        self.checkout_calls.append(
            {
                "customer_email": customer_email,
                "client_reference_id": client_reference_id,
                "price_id": price_id,
            }
        )
        return {
            "id": sid,
            "url": f"https://checkout.stripe.com/test/{sid}",
            "customer": f"cus_{client_reference_id}",
            "subscription": f"sub_{client_reference_id}",
        }

    def create_billing_portal_session(
        self,
        *,
        customer_id: str,
        return_url: str,
    ) -> dict[str, Any]:
        self.portal_calls.append({"customer_id": customer_id, "return_url": return_url})
        return {"url": f"https://billing.stripe.com/test/{customer_id}"}

    def retrieve_subscription(self, subscription_id: str) -> dict[str, Any]:
        self.retrieve_calls.append(subscription_id)
        return self.subscriptions.get(
            subscription_id,
            {
                "id": subscription_id,
                "status": "active",
                "customer": "cus_test_1",
                "current_period_end": 4102444800,
            },
        )