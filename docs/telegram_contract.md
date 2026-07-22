# Telegram Companion Contract (Этап 5 — Telegram)

## Purpose

Telegram-компаньон (ТЗ §3.6) — **дополняет**, не заменяет web-приложение.
Получает alerts/reminders, quick resume checks, job summaries и interview
prep prompts через Telegram Bot API (httpx напрямую, без SDK). Привязка
identity (ТЗ §3.1) связывает web-аккаунт с Telegram chat_id.

Companion **не дублирует бизнес-логику**: команды отображают готовые отчёты
из существующих сервисов (`VacancyFitService`, `CasePrepService`,
`ParseDiagnosticsService`, `ApplicationReminderService`).

## Identity linking (§3.1)

Web-пользователь (аутентифицирован, `data_processing_consent`) вызывает
`POST /api/v1/me/telegram/link` → сервис генерит **HMAC-signed stateless**
`link_token` (подпись = `JWT_SECRET_KEY`, TTL `TELEGRAM_LINK_TOKEN_TTL_MINUTES`,
по умолчанию 15 мин; образец — OAuth `state` из `oauth_service.py`). Возвращает
deep link `https://t.me/<bot_username>?start=<link_token>`.

Пользователь открывает бота → `/start <link_token>` → webhook verify'ит HMAC
+ exp → `TelegramLinkService.link_user` сохраняет `telegram_chat_id` (plain
pseudonymous, как `oauth_provider_id`), `telegram_username`, `telegram_linked_at`
+ audit event `telegram_link`. Ответ бота: `✅ Telegram привязан`.

Security:
- Токен не содержит chat_id → атакующий своим chat_id не привяжется к чужому
  user_id без валидного токена (валидный выдаёт только web-auth user).
- Stateless → не хранится в БД. Повторный `/start <token>` (в пределах TTL)
  идемпотентен.
- Один Telegram-аккаунт (chat_id) не управляет двумя user'ами одновременно:
  перелинковка chat_id к другому user очищает старого (`audit
  telegram_link_reassign`). Без unique-constraint — пересоздание аккаунта валидно.
- Unlink: `DELETE /me/telegram/link` (web, auth) или команда `/unlink` (бот).

## Commands

Парсится `update.message.text` (callback-query v1 не поддерживается — inline
кнопок нет). Все ответы — **plain text** (без `parse_mode`): Markdown/HTML
требуют эскейпинга, что хрупко для динамического контента (vacancy titles).
Сообщения обрезаются до 4000 символов (лимит Telegram 4096) с пометкой.

| command | source | что отдаёт |
|---|---|---|
| `/start [token]` | `TelegramLinkService` | привязка identity (см. выше) |
| `/help` | static | список команд |
| `/summary [vacancy_id]` | `VacancyFitService.build_vacancy_fit` | fit score, gap severity, readiness, сильные стороны/пробелы; без id — последняя вакансия |
| `/check` | `ParseDiagnosticsService` (cached в `FileExtraction.extracted_metadata_json["parse_diagnostics"]`) | потерянные фрагменты, структурные warnings, скрытый текст (anti-hack), метаданные |
| `/prep [vacancy_id]` | `CasePrepService.build_case_set` | до 3 кейсов (case_type, title, prompt, framework, time_guidance) |
| `/reminders` | `ApplicationReminderService.get_reminders` | до 5 напоминаний (draft_stale / ready_not_submitted / follow_up_missing) |
| `/list` | `VacancyRepository.list_by_user_id` | до 10 вакансий (короткий id + title + company) для `/summary`, `/prep` |
| `/unlink` | `TelegramLinkService.unlink` | отвязка |

Команды (кроме `/start`) от непривязанного chat_id → `🔒 Аккаунт не привязан`.
Ownership: чужая вакансия → `VacancyRepository.get_by_id` возвращает None →
`VacancyFitService` 404 → бот отвечает `❌ ...`, не падает.

## Proactive alerts (Celery beat)

`app.tasks.notification_tasks.dispatch_telegram_alerts` (beat, раз в час,
очередь `notification`) → `TelegramDispatchService.dispatch_pending_alerts`:

1. `UserRepository.list_telegram_subscribers` — users с `telegram_chat_id`
   AND `telegram_dispatch_enabled=true` AND `is_active=true`.
2. Для каждого: `ApplicationReminderService.get_reminders` (готовые напоминания).
3. Дедуп через `telegram_dispatch_log`: `dispatch_key` =
   `{reminder_type}:{application_id}:{YYYY-MM-DD}` → максимум 1 уведомление
   типа на application в день (UTC). `exists` — первый слой; `UniqueConstraint
   (user_id, dispatch_key)` — второй (гонка при двойном beat-запуске → savepoint
   rollback, не роняет батч).
4. `TelegramClient.send_message` (httpx). Ошибка отправки логируется, батч
   продолжается, лог-запись **не** создаётся (только при success).
5. Возвращает `{subscribers, dispatched, skipped, errors}`.

Per-user opt-in: `PATCH /me/telegram/dispatch` (`{dispatch_enabled: bool}`),
требует привязки. Глобальный флаг — `TELEGRAM_DISPATCH_ENABLED`.

## Endpoints

### Под api-prefix `/api/v1` (auth + `require_data_processing_consent`)

- `POST /me/telegram/link` → `TelegramLinkResponse` (`deep_link`, `expires_in_minutes`).
  503 если `TELEGRAM_BOT_USERNAME` не задан. Без commit — токен stateless.
- `GET /me/telegram/status` → `TelegramStatusResponse` (`linked`, `chat_id`,
  `username`, `linked_at`, `dispatch_enabled`). `chat_id` виден только самому user.
- `DELETE /me/telegram/link` → `TelegramStatusResponse` (unlink + audit).
- `PATCH /me/telegram/dispatch` → `TelegramStatusResponse` (toggle opt-in).
  400 если `dispatch_enabled=true` без привязки.

### Webhook (без prefix, без auth)

- `POST /webhooks/telegram` → `TelegramWebhookAck` (`{ok: true}`). Raw body,
  секрет `X-Telegram-Bot-Api-Secret-Token` verify через `hmac.compare_digest`.
  Без секрета в dev — warning + пропуск; в prod — 403. Невалидный JSON → 400.
  Ошибка отправки ответа — rollback + лог, не 500 (Telegram не ретраит).

## Security (ФЗ-152)

- `telegram_chat_id` — pseudonymous identifier (как `oauth_provider_id`),
  **не ПДн**; хранится plain (lookup-key для webhook chat_id → user). Не шифруется.
- Секреты (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`) — только в
  settings/env, **никогда в БД**. `link_token` — stateless HMAC, не хранится.
- Webhook-секрет обязателен в prod при `TELEGRAM_DISPATCH_ENABLED` (prod-гард
  в `validate_runtime_safety`); webhook дублирует проверку defensively.
- Логи: только user_id (UUID) и command. **Без chat_id, без текста сообщения**
  (может содержать ПДн). Текст ответа бота не логируется.
- Audit: `telegram_link`, `telegram_unlink`, `telegram_link_reassign`
  (через `log_auth_event`).

## Configuration (env)

```
TELEGRAM_BOT_TOKEN=              # <token> from @BotFather (required in prod)
TELEGRAM_WEBHOOK_SECRET=         # secret_token for X-Telegram-Bot-Api-Secret-Token (required in prod)
TELEGRAM_BOT_USERNAME=           # bot username without '@' (required in prod; for deep links)
TELEGRAM_LINK_TOKEN_TTL_MINUTES=15
TELEGRAM_DISPATCH_ENABLED=false  # global flag for proactive push
TELEGRAM_WEBHOOK_URL=             # for setWebhook setup (not runtime validation)
```

Production-гарды (`validate_runtime_safety`): при `TELEGRAM_DISPATCH_ENABLED=true`
обязательны `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `TELEGRAM_BOT_USERNAME`.

## Non-goals

- Не замена web UI — только отображение готовых отчётов, без AI-генерации,
  без редактирования резюме/вакансий.
- Не storage резюме — `/check` читает кэшированную диагностику, не переоткрывает файл.
- Не групповые чаты — только private chat_id (один user на аккаунт).
- Не voice/media/callback-query v1 — только text-команды.
- Не real-time — proactive push раз в час (Celery beat), не мгновенно.
- Не inline-кнопки (v1) — парсер готов, но UI не реализован.