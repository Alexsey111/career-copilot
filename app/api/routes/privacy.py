# app/api/routes/privacy.py

"""Права субъекта ПДн и политика конфиденциальности (ФЗ-152).

- ``GET /me/data/export`` — доступ к своим ПДн (ст.14): выгрузка всех
  персональных данных пользователя в виде JSON.
- ``DELETE /me/data`` — уничтожение ПДн (ст.17): каскадное удаление данных
  пользователя. Аудит-события (AuthEvent/DataTransferEvent) сохраняются с
  обезличиванием (user_id → NULL), как требует ст.19 для журнала учёта.
- ``GET /privacy/policy`` — уведомление об обработке ПДн (ст.18).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_current_active_user
from app.db.session import get_db_session
from app.models import (
    AuthEvent,
    CandidateProfile,
    DataTransferEvent,
    DocumentVersion,
    EvidenceSnippet,
    InterviewSession,
    User,
    UserConsent,
    Vacancy,
)
from app.schemas.json_contracts import StrictBaseModel
from app.services.auth_service import log_auth_event

router = APIRouter(tags=["privacy"])


PRIVACY_POLICY: dict[str, list[str] | str] = {
    "title": "Политика обработки персональных данных — Career Copilot",
    "controller": "Career Copilot (оператор ПДн)",
    "legal_basis": "ФЗ-152 «О персональных данных», ст. 6, 9, 18, 19.",
    "categories_of_data": [
        "Учётные данные (email, данные OAuth-логина)",
        "Профиль кандидата (ФИО, локация, опыт, образование, навыки)",
        "Содержимое документов (резюме, сопроводительные письма)",
        "Извлечённый из файлов текст",
        "Ответы и отзывы интервью",
        "Метаданные откликов и аналитика поиска работы",
    ],
    "purposes": [
        "Генерация резюме, сопроводительных писем, вопросов к интервью",
        "Анализ соответствия профиля вакансиям",
        "Хранение и управление профилем кандидата",
    ],
    "recipients": [
        "AI-провайдеры (обработчики) — для генерации и анализа; передача фиксируется в журнале data_transfer_events с основанием «согласие».",
        "Объектное хранилище (MinIO/S3) — для исходных файлов.",
    ],
    "legal_basis_for_processing": "Согласие субъекта ПДн (consent). Обработка "
    "и передача AI-провайдеру требуют активного согласия (ai_generation, "
    "data_processing).",
    "retention": "Данные хранятся до достижения целей обработки или до "
    "отзыва согласия/запроса на удаление. Журналы учёта передач и "
    "аутентификации обезличиваются и хранятся согласно требованиям ФЗ-152.",
    "security_measures": [
        "Шифрование чувствительных полей at-rest (Fernet, AES-128 + HMAC)",
        "Передача только по HTTPS/TLS; HSTS в production",
        "Шифрование OAuth-токенов в БД",
        "Аудит передач ПДн и событий аутентификации",
    ],
    "subject_rights": [
        "Доступ к своим ПДн: GET /api/v1/me/data/export",
        "Уничтожение ПДн: DELETE /api/v1/me/data",
        "Управление согласиями: /api/v1/consent/",
    ],
    "market_policies": {
        # Этап 7: переключатель юрисдикции. Фото/дата рождения/пол/возраст
        # не хранятся в профиле и не рендерятся ни для одного рынка by design.
        # Здесь зафиксированы декларативные нормы по юрисдикции.
        "RU": "Фото в резюме приветствуется (рыночная норма РФ). Возраст и пол не "
        "запрашиваются и не выводятся.",
        "EU": "Фото, дата рождения, пол, возраст не включаются в резюме "
        "(EU Directive 2000/78/EC; GDPR Art.9 special categories).",
        "US": "Фото, дата рождения, пол, возраст не включаются в резюме "
        "(EEOC; anti-discrimination).",
    },
}


class DataExportResponse(StrictBaseModel):
    user: dict
    profile: dict | None
    evidence_snippets: list[dict]
    document_versions: list[dict]
    interview_sessions: list[dict]
    vacancies: list[dict]
    consents: list[dict]
    auth_events: list[dict]
    data_transfer_events: list[dict]


@router.get("/privacy/policy")
async def get_privacy_policy() -> dict:
    return PRIVACY_POLICY


@router.get("/me/data/export", response_model=DataExportResponse)
async def export_my_data(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> DataExportResponse:
    user_id = current_user.id

    user_obj = (
        await session.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()

    profile = (
        await session.execute(
            select(CandidateProfile)
            .where(CandidateProfile.user_id == user_id)
            .options(
                selectinload(CandidateProfile.experiences),
                selectinload(CandidateProfile.achievements),
                selectinload(CandidateProfile.educations),
                selectinload(CandidateProfile.certificates),
                selectinload(CandidateProfile.languages),
                selectinload(CandidateProfile.links),
                selectinload(CandidateProfile.target_tracks),
            )
        )
    ).scalar_one_or_none()

    profile_dict = None
    if profile is not None:
        profile_dict = {
            "full_name": profile.full_name,
            "headline": profile.headline,
            "location": profile.location,
            "summary": profile.summary,
            "target_roles": profile.target_roles_json,
            "technologies": profile.technologies_json,
            "salary_expectation": str(profile.salary_expectation) if profile.salary_expectation else None,
            "experiences": [
                {"role": e.role, "company": e.company, "description": e.description_raw}
                for e in profile.experiences
            ],
            "educations": [
                {"institution": e.institution, "degree": e.degree}
                for e in profile.educations
            ],
            "certificates": [
                {"name": c.name, "issuer": c.issuer} for c in profile.certificates
            ],
            "languages": [
                {"language": l.language, "proficiency": l.proficiency}
                for l in profile.languages
            ],
            "links": [{"label": l.label, "url": l.url} for l in profile.links],
        }

    evidence = (
        await session.execute(
            select(EvidenceSnippet).where(EvidenceSnippet.user_id == user_id)
        )
    ).scalars().all()
    evidence_list = [
        {
            "source_type": e.source_type,
            "snippet_text": e.snippet_text,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in evidence
    ]

    docs = (
        await session.execute(
            select(DocumentVersion).where(DocumentVersion.user_id == user_id)
        )
    ).scalars().all()
    docs_list = [
        {
            "document_kind": d.document_kind,
            "rendered_text": d.rendered_text,
            "content_json": d.content_json,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in docs
    ]

    interviews = (
        await session.execute(
            select(InterviewSession).where(InterviewSession.user_id == user_id)
        )
    ).scalars().all()
    interviews_list = [
        {
            "answers_json": i.answers_json,
            "feedback_json": i.feedback_json,
            "created_at": i.created_at.isoformat() if i.created_at else None,
        }
        for i in interviews
    ]

    vacancies = (
        await session.execute(
            select(Vacancy).where(Vacancy.user_id == user_id)
        )
    ).scalars().all()
    vacancies_list = [
        {
            "title": v.title,
            "company": v.company,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        }
        for v in vacancies
    ]

    consents = (
        await session.execute(
            select(UserConsent).where(UserConsent.user_id == user_id)
        )
    ).scalars().all()
    consents_list = [
        {
            "consent_type": c.consent_type,
            "granted": c.granted,
            "granted_at": c.granted_at.isoformat() if c.granted_at else None,
            "revoked_at": c.revoked_at.isoformat() if c.revoked_at else None,
        }
        for c in consents
    ]

    auth_events = (
        await session.execute(
            select(AuthEvent).where(AuthEvent.user_id == user_id)
        )
    ).scalars().all()
    auth_events_list = [
        {
            "event_type": e.event_type,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in auth_events
    ]

    transfers = (
        await session.execute(
            select(DataTransferEvent).where(DataTransferEvent.user_id == user_id)
        )
    ).scalars().all()
    transfers_list = [
        {
            "recipient": t.recipient,
            "purpose": t.purpose,
            "data_categories": t.data_categories,
            "legal_basis": t.legal_basis,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in transfers
    ]

    return DataExportResponse(
        user={
            "email": user_obj.email if user_obj else current_user.email,
            "auth_provider": user_obj.auth_provider if user_obj else None,
            "is_verified": user_obj.is_verified if user_obj else None,
            "last_login_at": user_obj.last_login_at.isoformat()
            if user_obj and user_obj.last_login_at
            else None,
        },
        profile=profile_dict,
        evidence_snippets=evidence_list,
        document_versions=docs_list,
        interview_sessions=interviews_list,
        vacancies=vacancies_list,
        consents=consents_list,
        auth_events=auth_events_list,
        data_transfer_events=transfers_list,
    )


@router.delete("/me/data", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_data(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Уничтожение ПДн пользователя (ФЗ-152 ст.17).

    Каскадное удаление через ON DELETE CASCADE по user_id. Аудит-события
    (auth_events, data_transfer_events) сохраняются с обезличиванием
    (user_id → NULL) согласно ст.19 (журналы учёта).
    """
    user_id = current_user.id

    # Загружаем реальный ORM-объект пользователя (current_user может быть
    # зависимостью-заменной, не привязанной к сессии).
    user_obj = (
        await session.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if user_obj is None:
        return

    # Обезличивание журналов учёта (retain audit, drop subject link).
    await session.execute(
        delete(AuthEvent).where(AuthEvent.user_id == user_id)
    )
    await session.execute(
        delete(DataTransferEvent).where(DataTransferEvent.user_id == user_id)
    )

    # Фиксируем запрос на уничтожение до удаления субъекта (user_id уже
    # обнулён в журналах выше — пишем с email для аудита).
    await log_auth_event(
        session,
        event_type="data_erasure_requested",
        request=request,
        email=current_user.email,
    )

    # Удаление пользователя → каскадно удаляются profile, evidence, documents,
    # interviews, vacancies, consents, refresh_sessions и т.д.
    await session.delete(user_obj)
    await session.commit()