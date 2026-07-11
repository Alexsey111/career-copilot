# app/api/routes/consent.py

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_active_user
from app.db.session import get_db_session
from app.models import User
from app.schemas.json_contracts import StrictBaseModel
from app.services.auth_service import log_auth_event
from app.services.consent_service import ConsentService


router = APIRouter(prefix="/consent", tags=["consent"])


class ConsentGrantRequest(StrictBaseModel):
    consent_type: str


class ConsentResponse(StrictBaseModel):
    consent_type: str
    granted: bool
    granted_at: str | None = None
    revoked_at: str | None = None
    version: str | None = None


class ConsentCheckResponse(StrictBaseModel):
    all_granted: bool
    missing_required: list[str]
    consents: list[dict]


@router.get("/", response_model=list[dict])
async def list_consents(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[dict]:
    service = ConsentService()
    return await service.get_user_consents(session, user_id=current_user.id)


@router.post("/", response_model=ConsentResponse)
async def grant_consent(
    payload: ConsentGrantRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> ConsentResponse:
    service = ConsentService()
    try:
        result = await service.grant_consent(
            session,
            user_id=current_user.id,
            consent_type=payload.consent_type,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    await log_auth_event(
        session,
        event_type="consent_granted",
        request=request,
        user_id=current_user.id,
        email=current_user.email,
        meta={"consent_type": payload.consent_type},
    )
    await session.commit()

    return ConsentResponse(
        consent_type=result["consent_type"],
        granted=result["granted"],
        granted_at=result.get("granted_at"),
        version=result.get("version"),
    )


@router.delete("/{consent_type}", response_model=ConsentResponse)
async def revoke_consent(
    consent_type: str,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> ConsentResponse:
    service = ConsentService()
    try:
        result = await service.revoke_consent(
            session,
            user_id=current_user.id,
            consent_type=consent_type,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    await log_auth_event(
        session,
        event_type="consent_revoked",
        request=request,
        user_id=current_user.id,
        email=current_user.email,
        meta={"consent_type": consent_type},
    )
    await session.commit()

    return ConsentResponse(
        consent_type=result["consent_type"],
        granted=result["granted"],
        revoked_at=result.get("revoked_at"),
    )


@router.get("/check", response_model=ConsentCheckResponse)
async def check_consents(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> ConsentCheckResponse:
    service = ConsentService()
    result = await service.check_required_consents(
        session,
        user_id=current_user.id,
    )
    return ConsentCheckResponse(**result)


@router.get("/check/{consent_type}")
async def check_single_consent(
    consent_type: str,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    service = ConsentService()
    granted = await service.check_consent(
        session,
        user_id=current_user.id,
        consent_type=consent_type,
    )
    return {"consent_type": consent_type, "granted": granted}
