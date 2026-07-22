# tests/test_telegram_commands.py

"""Тесты команд бота (Этап 5) — unit-стиль через stub-сервисы (без HTTP/seed).

``TelegramCompanionService`` принимает репозитории/сервисы через конструктор
(DI), что позволяет подменять их стабами без сложного seed вакансий/профиля.
``handle_webhook_update`` вызывается напрямую (не через HTTP) — он возвращает
``(chat_id, reply_text)``.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException, status

from app.models import User
from app.services.telegram_companion_service import TelegramCompanionService
from factories.telegram_updates import make_message_update


# --- stubs ---


class StubVacancyRepo:
    def __init__(self, *, by_id=None, list_by_user=None):
        self._by_id = by_id or {}  # vacancy_id_hex -> vacancy
        self._list = list_by_user  # list or None

    async def get_by_id(self, session, vacancy_id, *, user_id):
        return self._by_id.get(str(vacancy_id))

    async def list_by_user_id(self, session, *, user_id):
        return self._list or []


class StubVacancyFitService:
    def __init__(self, fit=None, *, raise_404=False, raise_400=False):
        self._fit = fit
        self._raise_404 = raise_404
        self._raise_400 = raise_400

    async def build_vacancy_fit(self, session, *, vacancy_id, user_id):
        if self._raise_404:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "vacancy not found")
        if self._raise_400:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "vacancy analysis not found")
        return self._fit or {
            "overall_fit_score": 72,
            "gap_severity": "important",
            "readiness_recommendation": "Apply with caution",
            "evidence_coverage": {
                "strong": [{"requirement": "Python"}],
                "missing": [{"requirement": "Kubernetes"}],
            },
        }


class StubCasePrepService:
    def __init__(self, report=None):
        self._report = report

    async def build_case_set(self, session, *, user_id, vacancy_id):
        return self._report or {
            "cases": [
                {
                    "case_type": "system_design",
                    "title": "Design a URL shortener",
                    "prompt": "How would you scale it?",
                    "framework": "STAR",
                    "time_guidance": "30 min",
                }
            ],
            "meta": {"total": 1},
        }


class StubReminderService:
    def __init__(self, reminders=None):
        self._reminders = reminders or []

    async def get_reminders(self, session, *, user_id):
        return self._reminders


class StubSourceFileRepo:
    def __init__(self, source_file=None):
        self._source_file = source_file

    async def get_active_by_kind(self, session, *, user_id, file_kind):
        return self._source_file


class StubFileExtractionRepo:
    def __init__(self, extraction=None):
        self._extraction = extraction

    async def get_latest_for_source_file(self, session, *, source_file_id):
        return self._extraction


class StubLinkService:
    def __init__(self, *, token_user_id=None):
        self._token_user_id = token_user_id
        self.unlinked = False
        self.linked_chat_id = None

    def verify_link_token(self, token):
        return self._token_user_id

    async def link_user(self, session, *, user_id, chat_id, username=None, request=None):
        self.linked_chat_id = chat_id
        return SimpleNamespace(id=user_id, email="x@local.test")

    async def unlink(self, session, *, user_id, request=None):
        self.unlinked = True
        return SimpleNamespace(id=user_id, email="x@local.test")


def _service(
    *,
    vacancy_repo=None,
    vacancy_fit_service=None,
    case_prep_service=None,
    reminder_service=None,
    source_file_repo=None,
    file_extraction_repo=None,
    link_service=None,
    user_repo=None,
):
    return TelegramCompanionService(
        user_repo=user_repo,
        link_service=link_service,
        vacancy_repo=vacancy_repo,
        vacancy_fit_service=vacancy_fit_service,
        case_prep_service=case_prep_service,
        parse_diagnostics_service=None,  # not used when diagnostics pre-cached
        source_file_repo=source_file_repo,
        file_extraction_repo=file_extraction_repo,
        reminder_service=reminder_service,
    )


def _make_vacancy(vacancy_id=None, title="Senior Python", company="Acme"):
    return SimpleNamespace(id=vacancy_id or uuid4(), title=title, company=company)


# --- fixtures ---


@pytest.fixture
def linked_user_repo(test_user):
    """UserRepository wrapper returning test_user for a fixed chat_id."""
    repo = SimpleNamespace()

    async def get_by_telegram_chat_id(session, chat_id):
        if chat_id == "123456789":
            return test_user
        return None

    repo.get_by_telegram_chat_id = get_by_telegram_chat_id
    return repo


@pytest.fixture
def linked_chat_id():
    return "123456789"


# --- routing ---


class _UnlinkedUserRepo:
    async def get_by_telegram_chat_id(self, session, chat_id):
        return None


@pytest.mark.asyncio
async def test_unlinked_chat_replies_not_linked(db_session, test_user):
    svc = _service(user_repo=_UnlinkedUserRepo())
    result = await svc.handle_webhook_update(
        db_session, make_message_update("/summary", chat_id=999)
    )
    assert result is not None
    _chat, text = result
    assert "привязан" in text.lower()


@pytest.mark.asyncio
async def test_help_command(db_session, linked_user_repo, linked_chat_id):
    svc = _service(user_repo=linked_user_repo)
    result = await svc.handle_webhook_update(
        db_session, make_message_update("/help", chat_id=int(linked_chat_id))
    )
    _chat, text = result
    assert "/summary" in text and "/check" in text and "/reminders" in text


@pytest.mark.asyncio
async def test_unknown_command_returns_help(db_session, linked_user_repo, linked_chat_id):
    svc = _service(user_repo=linked_user_repo)
    result = await svc.handle_webhook_update(
        db_session, make_message_update("/bogus", chat_id=int(linked_chat_id))
    )
    _chat, text = result
    assert "/help" in text


@pytest.mark.asyncio
async def test_not_message_returns_none(db_session):
    svc = _service()
    assert await svc.handle_webhook_update(db_session, {"update_id": 1}) is None
    assert await svc.handle_webhook_update(
        db_session, {"update_id": 2, "message": {"chat": {"id": 1}}}
    ) is None  # no text


# --- /summary ---


@pytest.mark.asyncio
async def test_summary_latest_vacancy(db_session, linked_user_repo, linked_chat_id, test_user):
    vacancy = _make_vacancy()
    svc = _service(
        user_repo=linked_user_repo,
        vacancy_repo=StubVacancyRepo(list_by_user=[vacancy]),
        vacancy_fit_service=StubVacancyFitService(),
    )
    result = await svc.handle_webhook_update(
        db_session, make_message_update("/summary", chat_id=int(linked_chat_id))
    )
    _chat, text = result
    assert "Senior Python" in text
    assert "72" in text
    assert "Python" in text
    assert "Kubernetes" in text


@pytest.mark.asyncio
async def test_summary_by_id(db_session, linked_user_repo, linked_chat_id):
    vacancy = _make_vacancy()
    svc = _service(
        user_repo=linked_user_repo,
        vacancy_repo=StubVacancyRepo(by_id={str(vacancy.id): vacancy}),
        vacancy_fit_service=StubVacancyFitService(),
    )
    result = await svc.handle_webhook_update(
        db_session,
        make_message_update(f"/summary {vacancy.id}", chat_id=int(linked_chat_id)),
    )
    _chat, text = result
    assert "Senior Python" in text


@pytest.mark.asyncio
async def test_summary_invalid_id(db_session, linked_user_repo, linked_chat_id):
    svc = _service(user_repo=linked_user_repo, vacancy_repo=StubVacancyRepo())
    result = await svc.handle_webhook_update(
        db_session,
        make_message_update("/summary not-a-uuid", chat_id=int(linked_chat_id)),
    )
    _chat, text = result
    assert "нет вакансий" in text.lower() or "❌" in text


@pytest.mark.asyncio
async def test_summary_no_vacancies(db_session, linked_user_repo, linked_chat_id):
    svc = _service(user_repo=linked_user_repo, vacancy_repo=StubVacancyRepo())
    result = await svc.handle_webhook_update(
        db_session, make_message_update("/summary", chat_id=int(linked_chat_id))
    )
    _chat, text = result
    assert "нет вакансий" in text.lower()


@pytest.mark.asyncio
async def test_summary_foreign_vacancy_replies_error_not_500(
    db_session, linked_user_repo, linked_chat_id
):
    # get_by_id returns None → VacancyFitService raises 404 → bot replies ❌.
    svc = _service(
        user_repo=linked_user_repo,
        vacancy_repo=StubVacancyRepo(),  # by_id empty
        vacancy_fit_service=StubVacancyFitService(raise_404=True),
    )
    result = await svc.handle_webhook_update(
        db_session,
        make_message_update(f"/summary {uuid4()}", chat_id=int(linked_chat_id)),
    )
    _chat, text = result
    assert "❌" in text


# --- /prep ---


@pytest.mark.asyncio
async def test_prep_returns_cases(db_session, linked_user_repo, linked_chat_id):
    vacancy = _make_vacancy(title="Data Engineer")
    svc = _service(
        user_repo=linked_user_repo,
        vacancy_repo=StubVacancyRepo(list_by_user=[vacancy]),
        case_prep_service=StubCasePrepService(),
    )
    result = await svc.handle_webhook_update(
        db_session, make_message_update("/prep", chat_id=int(linked_chat_id))
    )
    _chat, text = result
    assert "Data Engineer" in text
    assert "system_design" in text
    assert "URL shortener" in text


@pytest.mark.asyncio
async def test_prep_no_cases_when_fit_missing(
    db_session, linked_user_repo, linked_chat_id
):
    vacancy = _make_vacancy()
    svc = _service(
        user_repo=linked_user_repo,
        vacancy_repo=StubVacancyRepo(list_by_user=[vacancy]),
        case_prep_service=StubCasePrepService(
            report={"cases": [], "meta": {"reason": "vacancy_analysis_or_profile_missing"}}
        ),
    )
    result = await svc.handle_webhook_update(
        db_session, make_message_update("/prep", chat_id=int(linked_chat_id))
    )
    _chat, text = result
    assert "анализ" in text.lower() or "профиль" in text.lower()


# --- /check ---


@pytest.mark.asyncio
async def test_check_no_resume(db_session, linked_user_repo, linked_chat_id):
    svc = _service(
        user_repo=linked_user_repo,
        source_file_repo=StubSourceFileRepo(source_file=None),
    )
    result = await svc.handle_webhook_update(
        db_session, make_message_update("/check", chat_id=int(linked_chat_id))
    )
    _chat, text = result
    assert "резюме" in text.lower()


@pytest.mark.asyncio
async def test_check_with_diagnostics(db_session, linked_user_repo, linked_chat_id):
    source_file = SimpleNamespace(
        id=uuid4(), original_name="resume.pdf", file_kind="resume"
    )
    extraction = SimpleNamespace(
        extracted_metadata_json={
            "parse_diagnostics": {
                "lost_blocks": [{"sample": "orphan text"}],
                "structural_warnings": [
                    {"severity": "high", "message": "table-like structure"}
                ],
                "hidden_text_findings": [],
                "metadata_exposure_warning": False,
            }
        },
        extracted_text="",
    )
    svc = _service(
        user_repo=linked_user_repo,
        source_file_repo=StubSourceFileRepo(source_file=source_file),
        file_extraction_repo=StubFileExtractionRepo(extraction=extraction),
    )
    result = await svc.handle_webhook_update(
        db_session, make_message_update("/check", chat_id=int(linked_chat_id))
    )
    _chat, text = result
    assert "resume.pdf" in text
    assert "orphan text" in text
    assert "table-like" in text


# --- /reminders ---


@pytest.mark.asyncio
async def test_reminders_empty(db_session, linked_user_repo, linked_chat_id):
    svc = _service(
        user_repo=linked_user_repo,
        reminder_service=StubReminderService(reminders=[]),
    )
    result = await svc.handle_webhook_update(
        db_session, make_message_update("/reminders", chat_id=int(linked_chat_id))
    )
    _chat, text = result
    assert "нет напоминаний" in text.lower()


@pytest.mark.asyncio
async def test_reminders_list(db_session, linked_user_repo, linked_chat_id):
    reminders = [
        SimpleNamespace(
            application_id=uuid4(),
            reminder_type="draft_stale",
            title="Черновик без активности",
            description="Отклик в черновике 20 дн.",
            days_since_event=20,
            created_at=None,
        )
    ]
    svc = _service(
        user_repo=linked_user_repo,
        reminder_service=StubReminderService(reminders=reminders),
    )
    result = await svc.handle_webhook_update(
        db_session, make_message_update("/reminders", chat_id=int(linked_chat_id))
    )
    _chat, text = result
    assert "Черновик без активности" in text
    assert "20" in text


# --- /list ---


@pytest.mark.asyncio
async def test_list_command(db_session, linked_user_repo, linked_chat_id):
    v1 = _make_vacancy(uuid4(), title="Backend Dev", company="Acme")
    v2 = _make_vacancy(uuid4(), title="Frontend Dev", company=None)
    svc = _service(
        user_repo=linked_user_repo,
        vacancy_repo=StubVacancyRepo(list_by_user=[v1, v2]),
    )
    result = await svc.handle_webhook_update(
        db_session, make_message_update("/list", chat_id=int(linked_chat_id))
    )
    _chat, text = result
    assert "Backend Dev" in text
    assert str(v1.id)[:8] in text


@pytest.mark.asyncio
async def test_list_empty(db_session, linked_user_repo, linked_chat_id):
    svc = _service(user_repo=linked_user_repo, vacancy_repo=StubVacancyRepo())
    result = await svc.handle_webhook_update(
        db_session, make_message_update("/list", chat_id=int(linked_chat_id))
    )
    _chat, text = result
    assert "нет вакансий" in text.lower()


# --- /unlink ---


@pytest.mark.asyncio
async def test_unlink_command(db_session, linked_user_repo, linked_chat_id):
    link_stub = StubLinkService()
    svc = _service(user_repo=linked_user_repo, link_service=link_stub)
    result = await svc.handle_webhook_update(
        db_session, make_message_update("/unlink", chat_id=int(linked_chat_id))
    )
    _chat, text = result
    assert "отвязан" in text.lower()
    assert link_stub.unlinked is True


# --- /start linking through the service (stubs) ---


@pytest.mark.asyncio
async def test_start_links_via_service_stubs(db_session, test_user):
    link_stub = StubLinkService(token_user_id=test_user.id)
    svc = _service(link_service=link_stub)
    result = await svc.handle_webhook_update(
        db_session, make_message_update("/start some-token", chat_id=42)
    )
    _chat, text = result
    assert "привязан" in text.lower()
    assert link_stub.linked_chat_id == "42"


@pytest.mark.asyncio
async def test_start_invalid_token_replies_error(db_session):
    link_stub = StubLinkService(token_user_id=None)
    svc = _service(link_service=link_stub)
    result = await svc.handle_webhook_update(
        db_session, make_message_update("/start bad-token", chat_id=42)
    )
    _chat, text = result
    assert "недействительна" in text.lower() or "истекла" in text.lower()
    assert link_stub.linked_chat_id is None


@pytest.mark.asyncio
async def test_start_without_token_replies_help_text(db_session):
    svc = _service(link_service=StubLinkService())
    result = await svc.handle_webhook_update(
        db_session, make_message_update("/start", chat_id=42)
    )
    _chat, text = result
    assert "привязк" in text.lower() or "ссылк" in text.lower()


# --- truncation ---


@pytest.mark.asyncio
async def test_long_message_truncated(db_session, linked_user_repo, linked_chat_id):
    long_title = "X" * 5000
    vacancy = _make_vacancy(title=long_title)
    svc = _service(
        user_repo=linked_user_repo,
        vacancy_repo=StubVacancyRepo(list_by_user=[vacancy]),
        vacancy_fit_service=StubVacancyFitService(),
    )
    result = await svc.handle_webhook_update(
        db_session, make_message_update("/summary", chat_id=int(linked_chat_id))
    )
    _chat, text = result
    assert len(text) <= 4096
    assert "ещё" in text