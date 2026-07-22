# app/services/telegram_companion_service.py

"""Webhook-маршрутизатор команд Telegram-бота (Этап 5, ТЗ §3.6).

Companion, not replacement: команды бота отображают готовые отчёты из
существующих сервисов — **новой бизнес-логики нет**.

Источники контента:
- ``/summary`` → ``VacancyFitService.build_vacancy_fit`` (job summary, fit score).
- ``/prep`` → ``CasePrepService.build_case_set`` (interview prep prompts).
- ``/check`` → ``ParseDiagnosticsService`` (quick resume check, ATS-diagnostics).
- ``/reminders`` → ``ApplicationReminderService.get_reminders`` (reminders).
- ``/list`` → ``VacancyRepository.list_by_user_id`` (vacancy ids для /summary /prep).
- ``/start <token>`` → ``TelegramLinkService`` (привязка identity, §3.1).
- ``/unlink`` → ``TelegramLinkService.unlink``.

Security/privacy: логируем только user_id и command (без chat_id, без текста
сообщения — может содержать ПДн). Все ответы — plain text (без parse_mode):
Telegram Markdown/HTML требуют эскейпинга, что хрупко для динамического
контента (vacancy titles, requirement text). Сообщения обрезаются до 4000
символов (лимит Telegram 4096) с пометкой.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.file_extraction_repository import FileExtractionRepository
from app.repositories.source_file_repository import SourceFileRepository
from app.repositories.user_repository import UserRepository
from app.repositories.vacancy_repository import VacancyRepository
from app.services.application_reminder_service import ApplicationReminderService
from app.services.case_prep_service import CasePrepService
from app.services.parse_diagnostics_service import ParseDiagnosticsService
from app.services.resume_parser_service import ParsedResume
from app.services.telegram_link_service import TelegramLinkService
from app.services.vacancy_fit_service import VacancyFitService

logger = logging.getLogger(__name__)

_MAX_MESSAGE_LEN = 4000

_HELP_TEXT = (
    "career-copilot — команды бота:\n"
    "/help — этот список\n"
    "/summary [vacancy_id] — сводка по вакансии (fit, пробелы)\n"
    "/check — экспресс-проверка резюме (ATS-диагностика)\n"
    "/prep [vacancy_id] — кейсы для подготовки к интервью\n"
    "/reminders — напоминания по откликам\n"
    "/list — список вакансий (id для /summary, /prep)\n"
    "/unlink — отвязать этот Telegram от аккаунта\n\n"
    "Ссылку для привязки нового аккаунта можно получить в web-приложении."
)


class TelegramCompanionService:
    def __init__(
        self,
        *,
        user_repo: UserRepository | None = None,
        link_service: TelegramLinkService | None = None,
        vacancy_repo: VacancyRepository | None = None,
        vacancy_fit_service: VacancyFitService | None = None,
        case_prep_service: CasePrepService | None = None,
        parse_diagnostics_service: ParseDiagnosticsService | None = None,
        source_file_repo: SourceFileRepository | None = None,
        file_extraction_repo: FileExtractionRepository | None = None,
        reminder_service: ApplicationReminderService | None = None,
    ) -> None:
        self.user_repo = user_repo or UserRepository()
        self.link_service = link_service or TelegramLinkService()
        self.vacancy_repo = vacancy_repo or VacancyRepository()
        self.vacancy_fit_service = vacancy_fit_service or VacancyFitService()
        self.case_prep_service = case_prep_service or CasePrepService()
        self.parse_diagnostics_service = parse_diagnostics_service or ParseDiagnosticsService()
        self.source_file_repo = source_file_repo or SourceFileRepository()
        self.file_extraction_repo = file_extraction_repo or FileExtractionRepository()
        self.reminder_service = reminder_service or ApplicationReminderService()

    async def handle_webhook_update(
        self,
        session: AsyncSession,
        update: dict[str, Any],
        *,
        request: Request | None = None,
    ) -> tuple[str, str] | None:
        """Парсит update, маршрутизирует команду. Возвращает (chat_id, reply)
        или None (не message — ack Telegram 200, без действия).

        Callback-query v1 не поддерживается (inline-кнопок нет) → None.
        """
        message = update.get("message")
        if not isinstance(message, dict):
            return None

        chat = message.get("chat") or {}
        chat_id_raw = chat.get("id")
        if chat_id_raw is None:
            return None
        chat_id = str(chat_id_raw)

        text = str(message.get("text") or "").strip()
        if not text:
            return None

        from_user = message.get("from") or {}
        tg_username = from_user.get("username")

        parts = text.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1].strip() if len(parts) > 1 else ""

        try:
            reply = await self._route(
                session,
                command=command,
                args=args,
                chat_id=chat_id,
                tg_username=tg_username,
                request=request,
            )
        except HTTPException as exc:
            # ownership/business-ошибки сервисов → текстовый ответ, не 500.
            reply = f"❌ {exc.detail}"
        except Exception:  # noqa: BLE001
            logger.exception("telegram command failed", extra={"command": command})
            reply = "⚠️ Внутренняя ошибка. Попробуйте /help."

        logger.info("telegram command", extra={"command": command})
        return chat_id, self._truncate(reply)

    # --- routing ---

    async def _route(
        self,
        session: AsyncSession,
        *,
        command: str,
        args: str,
        chat_id: str,
        tg_username: str | None,
        request: Request | None,
    ) -> str:
        if command == "/start":
            return await self._handle_start(
                session, args=args, chat_id=chat_id, tg_username=tg_username, request=request
            )
        if command == "/help":
            # /help доступен без привязки (публичная справка).
            return _HELP_TEXT

        # Все остальные команды требуют привязанного аккаунта.
        user = await self.user_repo.get_by_telegram_chat_id(session, chat_id)
        if user is None:
            return "🔒 Аккаунт не привязан. Откройте ссылку для привязки из web-приложения."

        if command == "/summary":
            return await self._handle_summary(session, user_id=user.id, args=args)
        if command == "/check":
            return await self._handle_check(session, user_id=user.id)
        if command == "/prep":
            return await self._handle_prep(session, user_id=user.id, args=args)
        if command == "/reminders":
            return await self._handle_reminders(session, user_id=user.id)
        if command == "/list":
            return await self._handle_list(session, user_id=user.id)
        if command == "/unlink":
            await self.link_service.unlink(session, user_id=user.id, request=request)
            return "❌ Telegram отвязан от аккаунта. Привязку можно повторить через web."
        # unknown / plain text
        return _HELP_TEXT

    # --- /start (linking) ---

    async def _handle_start(
        self,
        session: AsyncSession,
        *,
        args: str,
        chat_id: str,
        tg_username: str | None,
        request: Request | None,
    ) -> str:
        if not args:
            return (
                "Привет! Я career-copilot — компаньон для поиска работы.\n"
                "Чтобы привязать аккаунт, откройте ссылку из web-приложения.\n"
                "/help — список команд."
            )
        user_id = self.link_service.verify_link_token(args)
        if user_id is None:
            return "❌ Ссылка недействительна или истекла. Получите новую в web-приложении."
        await self.link_service.link_user(
            session,
            user_id=user_id,
            chat_id=chat_id,
            username=tg_username,
            request=request,
        )
        return "✅ Telegram привязан к аккаунту. Команды — /help"

    # --- /summary (vacancy fit) ---

    async def _handle_summary(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        args: str,
    ) -> str:
        vacancy, vacancy_id = await self._resolve_vacancy(session, user_id=user_id, args=args)
        if vacancy is None:
            return "❌ Нет вакансий. Импортируйте вакансию в web-приложении и запустите анализ."
        fit = await self.vacancy_fit_service.build_vacancy_fit(
            session, vacancy_id=vacancy.id, user_id=user_id
        )
        return self._format_vacancy_fit(fit=fit, vacancy=vacancy)

    @staticmethod
    def _format_vacancy_fit(*, fit: dict[str, Any], vacancy: Any) -> str:
        title = getattr(vacancy, "title", "") or "(без названия)"
        company = getattr(vacancy, "company", "") or ""
        header = f"Сводка по вакансии: {title}"
        if company:
            header += f" @ {company}"
        overall = fit.get("overall_fit_score")
        gap = fit.get("gap_severity")
        readiness = fit.get("readiness_recommendation")
        lines = [
            header,
            f"Fit: {overall}/100",
            f"Пробелы: {gap}",
            f"Рекомендация: {readiness}",
            "",
            "Сильные стороны:",
        ]
        strong = (fit.get("evidence_coverage") or {}).get("strong") or []
        if strong:
            for item in strong[:5]:
                lines.append(f"  • {item.get('requirement')}")
        else:
            lines.append("  — нет подтверждённых доказательств")
        missing = (fit.get("evidence_coverage") or {}).get("missing") or []
        if missing:
            lines.append("")
            lines.append("Пробелы (требуют подтверждения):")
            for item in missing[:5]:
                lines.append(f"  • {item.get('requirement')}")
        lines.append("")
        lines.append("Подробно — в web-приложении.")
        return "\n".join(lines)

    # --- /prep (interview cases) ---

    async def _handle_prep(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        args: str,
    ) -> str:
        vacancy, vacancy_id = await self._resolve_vacancy(session, user_id=user_id, args=args)
        if vacancy is None:
            return "❌ Нет вакансий. Импортируйте вакансию в web-приложении и запустите анализ."
        report = await self.case_prep_service.build_case_set(
            session, user_id=user_id, vacancy_id=vacancy.id
        )
        cases = report.get("cases") or []
        if not cases:
            reason = (report.get("meta") or {}).get("reason")
            if reason == "vacancy_analysis_or_profile_missing":
                return "❌ Анализ вакансии или профиль не готовы. Запустите их в web-приложении."
            return "Кейсов пока нет. Запустите анализ вакансии в web-приложении."
        lines = [f"Кейсы для подготовки: {getattr(vacancy, 'title', '') or ''}", ""]
        for case in cases[:3]:
            lines.append(f"[{case.get('case_type')}] {case.get('title')}")
            prompt = case.get("prompt")
            if prompt:
                lines.append(f"  {prompt}")
            framework = case.get("framework")
            if framework:
                lines.append(f"  Фреймворк: {framework}")
            time_guidance = case.get("time_guidance")
            if time_guidance:
                lines.append(f"  Время: {time_guidance}")
            lines.append("")
        lines.append("Полные кейсы — в web-приложении.")
        return "\n".join(lines)

    # --- /check (resume diagnostics) ---

    async def _handle_check(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
    ) -> str:
        source_file = await self.source_file_repo.get_active_by_kind(
            session, user_id=user_id, file_kind="resume"
        )
        if source_file is None:
            return "❌ Нет активного резюме. Загрузите резюме в web-приложении."
        extraction = await self.file_extraction_repo.get_latest_for_source_file(
            session, source_file_id=source_file.id
        )
        if extraction is None:
            return "❌ Резюме ещё не распарсено. Импортируйте его в web-приложении."

        metadata = extraction.extracted_metadata_json or {}
        diagnostics_dict = metadata.get("parse_diagnostics")
        if not diagnostics_dict:
            # Совместимость со старыми extractions: частичный пересчёт из текста.
            detected = metadata.get("detected_format") or "text"
            partial = ParsedResume(
                text=extraction.extracted_text or "",
                detected_format=detected,
                metadata={
                    "diagnostics_seed": {
                        "zero_width": {"count": 0, "sample": ""},
                        "hidden_text": [],
                        "file_metadata": {},
                    },
                },
            )
            diagnostics_dict = self.parse_diagnostics_service.build_report(partial).as_dict()
        return self._format_diagnostics(diagnostics_dict, filename=source_file.original_name)

    @staticmethod
    def _format_diagnostics(report: dict[str, Any], *, filename: str | None) -> str:
        lines = [f"Экспресс-проверка резюме: {filename or ''}", ""]

        lost = report.get("lost_blocks") or []
        if lost:
            lines.append(f"⚠️ Потерянные фрагменты ({len(lost)}):")
            for block in lost[:5]:
                lines.append(f"  • {block.get('sample')}")
            lines.append("")

        warnings = report.get("structural_warnings") or []
        if warnings:
            lines.append("Структурные предупреждения:")
            for w in warnings[:5]:
                lines.append(f"  • [{w.get('severity')}] {w.get('message')}")
            lines.append("")

        hidden = report.get("hidden_text_findings") or []
        if hidden:
            lines.append("🚨 Скрытый текст (anti-hack):")
            for h in hidden[:5]:
                lines.append(f"  • {h.get('kind')}: {h.get('sample')}")
            lines.append("")

        if report.get("metadata_exposure_warning"):
            lines.append("🚨 Метаданные файла раскрывают ПДн (автор/производитель).")
            lines.append("")

        if not lost and not warnings and not hidden:
            lines.append("✅ Серьёзных проблем не найдено.")
        lines.append("Полный отчёт — в web-приложении.")
        return "\n".join(lines)

    # --- /reminders ---

    async def _handle_reminders(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
    ) -> str:
        reminders = await self.reminder_service.get_reminders(session, user_id=user_id)
        if not reminders:
            return "✅ Нет напоминаний. Всё под контролем."
        lines = ["Напоминания по откликам:", ""]
        for r in reminders[:5]:
            lines.append(
                f"• {r.title} ({r.days_since_event} дн.)\n  {r.description}"
            )
        if len(reminders) > 5:
            lines.append("")
            lines.append(f"… и ещё {len(reminders) - 5}. Подробно — в web-приложении.")
        return "\n".join(lines)

    # --- /list ---

    async def _handle_list(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
    ) -> str:
        vacancies = await self.vacancy_repo.list_by_user_id(session, user_id=user_id)
        if not vacancies:
            return "Нет вакансий. Импортируйте вакансию в web-приложении."
        lines = ["Ваши вакансии (id для /summary, /prep):", ""]
        for v in vacancies[:10]:
            short_id = str(v.id)[:8]
            title = v.title or "(без названия)"
            company = v.company or ""
            company_part = f" @ {company}" if company else ""
            lines.append(f"{short_id} | {title}{company_part}")
        if len(vacancies) > 10:
            lines.append("")
            lines.append(f"… и ещё {len(vacancies) - 10}.")
        return "\n".join(lines)

    # --- helpers ---

    async def _resolve_vacancy(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        args: str,
    ) -> tuple[Any, UUID | None]:
        """Если args — валидный UUID → vacancy по id (ownership). Без args —
        последняя вакансия. Возвращает (vacancy_or_None, vacancy_id_or_None)."""
        if args:
            try:
                vacancy_id = UUID(args)
            except ValueError:
                return None, None
            vacancy = await self.vacancy_repo.get_by_id(session, vacancy_id, user_id=user_id)
            return vacancy, vacancy_id
        vacancies = await self.vacancy_repo.list_by_user_id(session, user_id=user_id)
        if not vacancies:
            return None, None
        return vacancies[0], vacancies[0].id

    @staticmethod
    def _truncate(text: str) -> str:
        if len(text) <= _MAX_MESSAGE_LEN:
            return text
        overflow = len(text) - _MAX_MESSAGE_LEN
        return text[:_MAX_MESSAGE_LEN] + f"\n\n… +{overflow} ещё. См. web."