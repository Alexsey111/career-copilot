# Billing Contract (Этап 4 — Billing/Stripe)

## Purpose

Контур биллинга управляет доступом к платным возможностям через тарифные
планы и free-tier квоты (ТЗ §3.5). Stripe (официальный SDK) используется как
платёжный провайдер: subscription lifecycle, invoices, webhooks. Metering
считает использование AI/загрузок/генераций; enforcement жёсткий — превышение
free-tier возвращает **402 Payment Required**.

## Plans

- `free` — пользователь без записи `Subscription` трактуется как `free` (in-memory
  view в сервисе; запись создаётся только при первом checkout).
- `paid_monthly` — unlimited (квоты не применяются при активной подписке).

`Subscription` — одна запись на пользователя (`UniqueConstraint(user_id)`).
`stripe_customer_id` — PII/finance → **EncryptedText** (ФЗ-152 ст.19).
`stripe_subscription_id` — публичный Stripe-идентификатор (`sub_xxx`), не ПДн →
plain `String` (нужен для webhook lookup без шифрования).

## Subscription statuses

- `active` — доступ к платным возможностям.
- `past_due` — доступ сохраняется (льготный период не моделируется отдельно),
  Stripe повторяет списание.
- `canceled` — доступ закрыт (по `customer.subscription.deleted`).
- `ended` — нет доступа (incomplete/expired/paused/unknown).

Маппинг статусов Stripe → наших: `active|trialing → active`,
`past_due|unpaid → past_due`, `canceled → canceled`, прочее → `ended`.

## Quota actions и metering

Три действия квот со скользящим окном `BILLING_QUOTA_WINDOW_DAYS` (default 30):

| action | metering source | free-tier limit env |
|---|---|---|
| `ai_request` | `AIRun` (исключая `GENERATED_OUTPUT_WORKFLOWS`) | `BILLING_FREE_TIER_AI_REQUESTS_LIMIT` (50) |
| `doc_upload` | `SourceFile` | `BILLING_FREE_TIER_DOC_UPLOADS_LIMIT` (10) |
| `generated_output` | `DocumentVersion` (root-версии: `derived_from_id IS NULL`, `document_kind` ∈ {`resume`,`cover_letter`}) | `BILLING_FREE_TIER_GENERATED_OUTPUTS_LIMIT` (5) |

**Важно (обоснование metering):** `generated_output` считается по
`DocumentVersion`, **не** по `AIRun` — `generate_resume`/`generate_cover_letter`
в production детерминированные (`use_ai_enhancement=False` по умолчанию) и **не
трассируют AIRun**; счёт по AIRun всегда давал бы 0. `ai_request` исключает
`GENERATED_OUTPUT_WORKFLOWS = {resume_tailoring, cover_letter_enhance}`, чтобы
при включённом AI-усилении генерация документа не считалась дважды.

`GENERATED_OUTPUT_WORKFLOWS` содержит только workflow генерации (generate-path):
`resume_tailoring` (используется `generate_resume`) и `cover_letter_enhance`
(используется `generate_cover_letter` с AI-усилением). Ручной enhance идёт через
**отдельные** workflow `resume_enhance` и `cover_letter_improve` (симметричные
generate-path), которые **не** исключаются → тарифицируются как `ai_request`.
Без этого разделения `cover_letter_enhance` использовался бы обоими путями, и
ручной enhance не учитывался бы ни в одной квоте (derived-DocumentVersion не
считается как `generated_output`, а workflow исключён из `ai_request`).

`GENERATED_OUTPUT_KINDS = {resume, cover_letter}`. Root-версии
(`derived_from_id IS NULL`) = generation; derived-версии (`derived_from_id` от
родителя, создаются `enhance_*`) НЕ считаются как `generated_output` (их AI-вызов
считается как `ai_request`).

## Enforcement (402)

`require_quota(action)` — FastAPI-зависимость (factory), проверяет квоту перед
действием. paid_monthly + активная подписка → unlimited. Превышение free-tier →
`402 Payment Required` со структурированным `detail`:

```json
{
  "action": "ai_request",
  "plan": "free",
  "used": 51,
  "limit": 50,
  "reason": "free-tier quota exceeded for 'ai_request': used 51 of 50"
}
```

Подключена в дополнение к consent-зависимостям существующих эндпоинтов:

- `generated_output`: `POST /documents/resumes/generate`, `POST /documents/letters/generate`.
- `ai_request`: `POST /documents/resumes/{id}/enhance`, `POST /documents/letters/{id}/enhance`,
  `POST /profile/extract-structured`, `POST /profile/extract-achievements`,
  `POST /profile/repository-achievements/generate`,
  `POST /interviews/{id}/answer/coach`, `POST /interviews/{id}/answer/mock`,
  `POST /interviews/{id}/answer/advisory`.
- `doc_upload`: `POST /files/upload`.

## Endpoints (под api-prefix `/api/v1`)

### `POST /api/v1/billing/checkout` → `CheckoutResponse`
Создаёт Stripe Checkout Session (subscription mode) для перехода на paid.
`client_reference_id` = user_id (связь webhook'а с пользователем). 503 если не
сконфигурирован `STRIPE_PRICE_PAID_MONTHLY_ID`.

```json
{"checkout_session_id": "cs_test_...", "checkout_url": "https://checkout.stripe.com/..."}
```

### `POST /api/v1/billing/portal` → `PortalResponse`
Stripe Billing Portal (управление подпиской). 404 если нет paid-подписки
(требуется `stripe_customer_id`).

### `GET /api/v1/me/billing/subscription` → `MySubscriptionResponse`
Текущий план, статус, Stripe-refs, период + usage по всем действиям.
Пользователь без записи → `{plan: "free", status: "active", ...}`.
`usage[*].limit = null` для платного плана (unlimited).

## Webhook

### `POST /webhooks/stripe` (raw, без api-prefix, без auth)
Stripe шлёт события на корневой путь. Подпись verified через
`stripe.Webhook.construct_event(payload, sig_header, secret, tolerance)`.
Невалидная подпись → 400. Idempotency через `billing_events`
(`stripe_event_id` UNIQUE): ретраи Stripe не дублируют эффект. Повтор с
`processed=True` → `{processed: true, duplicate: true}`.

Обрабатываемые события (минимальный lifecycle подписки):

- `checkout.session.completed` → создаёт/активирует `Subscription`
  (`plan=paid_monthly`, `status=active`, `stripe_customer_id`,
  `stripe_subscription_id`, `current_period_end`).
- `customer.subscription.updated` → обновляет `status`/`current_period_end`.
  При переходе в `canceled`/`ended` — `canceled_at` сохраняется (если уже был) или
  фиксируется `now`; при возврате в `active`/`past_due` — `canceled_at` сбрасывается
  в `NULL` (реактивация).
- `customer.subscription.deleted` → `status=canceled`, `canceled_at=now`,
  `current_period_end=NULL`.
- `invoice.payment_succeeded` → `status=active`, `current_period_end`
  (сохраняется старый, если Stripe не прислал в инвойсе).
- `invoice.payment_failed` → `status=past_due` (`current_period_end` без изменений).

`SubscriptionRepository.update` использует sentinel для различения «поле не
передано» (не трогать) от `None` (сбросить в NULL) — это позволяет корректно
сбрасывать `current_period_end`/`canceled_at`/`stripe_*_id` при отмене/реактивации/re-checkout.

Неизвестный тип → успешно игнорируется (`processed=true`). Ошибка обработки →
400 (Stripe ретраит), запись `billing_events(processed=False)` не
коммитится (следуя паттерну сервиса: commit в эндпоинте, rollback при exception).

**Known limitation:** идемпотентность рассчитана на последовательные ретраи Stripe
(одна транзакция на webhook). Параллельные доставленные копии одного event могут
дать `IntegrityError` у проигравшего (500 вместо 400); эффект при этом не
дублируется (UNIQUE `stripe_event_id`). Корректная обработка параллелизма через
savepoint — tech-debt (Stripe ретраит последовательно).

`billing_events.payload_json` хранит только `id`+`type` (без ПДн вне
`stripe_customer_id`, который уже зашифрован в `Subscription`).

## Configuration (env)

```
STRIPE_SECRET_KEY=              # sk_test_* / sk_live_* (required in prod)
STRIPE_WEBHOOK_SECRET=          # whsec_* (required in prod)
STRIPE_WEBHOOK_TOLERANCE=300
STRIPE_PRICE_PAID_MONTHLY_ID=    # price_xxx (required in prod)
STRIPE_PAID_MONTHLY_AMOUNT=0     # display-only, minor units
STRIPE_PAID_PLAN_NAME=paid_monthly
BILLING_FREE_TIER_AI_REQUESTS_LIMIT=50
BILLING_FREE_TIER_DOC_UPLOADS_LIMIT=10
BILLING_FREE_TIER_GENERATED_OUTPUTS_LIMIT=5
BILLING_QUOTA_WINDOW_DAYS=30
BILLING_CHECKOUT_SUCCESS_URL=
BILLING_CHECKOUT_CANCEL_URL=
BILLING_PORTAL_RETURN_URL=
```

Production-гарды (`validate_runtime_safety`): `STRIPE_SECRET_KEY`,
`STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_PAID_MONTHLY_ID` обязательны в prod.

## Non-goals

- Без Stripe metered usage reporting (quota enforcement локальное, soft).
- Без отдельных тарифов/аддонов — только `free`/`paid_monthly`.
- Без хранения платёжных данных карт (PCI) — только Stripe-ресурс-идентификаторы.
- Без webhook-подписи для endpoints checkout/portal — auth через access token.
- `billing_events` — не финансовый аудит, а idempotency-лог.