# app\api\routes\auth.py

from __future__ import annotations

from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.models import PasswordResetToken, User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    LoginRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    PasswordResetRequestResponse,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from app.security.dependencies import get_current_active_user
from app.security.passwords import hash_password, verify_password
from app.security.tokens import generate_refresh_token, hash_refresh_token
from app.services.auth_service import (
    enforce_login_throttle,
    get_password_reset_expires,
    get_session_by_token_hash,
    issue_tokens,
    log_auth_event,
    revoke_all_user_sessions,
    utcnow,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
async def register(
    body: RegisterRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    repo = UserRepository()
    existing = await repo.get_by_email(session, body.email.lower())
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = await repo.create(
        session,
        email=body.email.lower(),
        password_hash=hash_password(body.password),
        auth_provider="email",
    )
    await session.commit()
    await session.refresh(user)
    await log_auth_event(
        session,
        event_type="register",
        request=request,
        user_id=user.id,
        email=user.email,
    )

    return await issue_tokens(session, user, request)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    repo = UserRepository()
    await enforce_login_throttle(
        session,
        request=request,
        email=body.email,
    )
    user = await repo.get_by_email(session, body.email.lower())
    if (
        user is None
        or not user.password_hash
        or not verify_password(body.password, user.password_hash)
    ):
        await log_auth_event(
            session,
            event_type="login_failed",
            request=request,
            email=body.email,
        )
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account deactivated",
        )

    user.last_login_at = utcnow()
    await log_auth_event(
        session,
        event_type="login_success",
        request=request,
        user_id=user.id,
        email=user.email,
    )
    await session.commit()

    return await issue_tokens(session, user, request)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    token_hash = hash_refresh_token(body.refresh_token)
    session_obj = await get_session_by_token_hash(session, token_hash)

    if session_obj is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked refresh token",
        )

    if session_obj.revoked_at is not None:
        await revoke_all_user_sessions(session, session_obj.user_id)
        await log_auth_event(
            session,
            event_type="refresh_reuse_detected",
            request=request,
            user_id=session_obj.user_id,
        )
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token reuse detected",
        )

    if session_obj.expires_at <= utcnow():
        session_obj.revoked_at = utcnow()
        await log_auth_event(
            session,
            event_type="refresh_expired",
            request=request,
            user_id=session_obj.user_id,
        )
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired",
        )

    repo = UserRepository()
    user = await repo.get_by_id(session, session_obj.user_id)
    if user is None or not user.is_active:
        session_obj.revoked_at = utcnow()
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User invalid or inactive",
        )

    session_obj.revoked_at = utcnow()
    await log_auth_event(
        session,
        event_type="refresh_success",
        request=request,
        user_id=user.id,
        email=user.email,
    )
    await session.commit()

    return await issue_tokens(session, user, request)


@router.post("/logout")
async def logout(
    body: RefreshRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    token_hash = hash_refresh_token(body.refresh_token)
    session_obj = await get_session_by_token_hash(session, token_hash)

    if session_obj is not None and session_obj.revoked_at is None:
        session_obj.revoked_at = utcnow()
        await log_auth_event(
            session,
            event_type="logout",
            request=request,
            user_id=session_obj.user_id,
        )
        await session.commit()

    return {"status": "ok"}


@router.post("/logout-all")
async def logout_all(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    await revoke_all_user_sessions(session, current_user.id)
    await log_auth_event(
        session,
        event_type="logout_all",
        request=request,
        user_id=current_user.id,
    )
    await session.commit()
    return {"status": "ok"}


@router.post("/password-reset/request", response_model=PasswordResetRequestResponse)
async def request_password_reset(
    body: PasswordResetRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> PasswordResetRequestResponse:
    repo = UserRepository()
    user = await repo.get_by_email(session, body.email.lower())

    if user is None or not user.is_active:
        await log_auth_event(
            session,
            event_type="password_reset_requested",
            request=request,
            email=body.email,
            meta={"user_found": False},
        )
        await session.commit()
        return PasswordResetRequestResponse()

    reset_plain = generate_refresh_token()
    reset_hash = hash_refresh_token(reset_plain)

    session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=reset_hash,
            expires_at=get_password_reset_expires(),
        )
    )

    await log_auth_event(
        session,
        event_type="password_reset_requested",
        request=request,
        user_id=user.id,
        email=user.email,
        meta={"user_found": True},
    )
    await session.commit()

    return PasswordResetRequestResponse(reset_token=reset_plain)


@router.post("/password-reset/confirm")
async def confirm_password_reset(
    body: PasswordResetConfirmRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    token_hash = hash_refresh_token(body.reset_token)

    result = await session.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash,
        )
    )
    reset_token = result.scalars().first()

    if reset_token is None:
        await log_auth_event(
            session,
            event_type="password_reset_invalid_token",
            request=request,
        )
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired reset token",
        )

    if reset_token.used_at is not None or reset_token.expires_at <= utcnow():
        await log_auth_event(
            session,
            event_type="password_reset_invalid_token",
            request=request,
            user_id=reset_token.user_id,
        )
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired reset token",
        )

    repo = UserRepository()
    user = await repo.get_by_id(session, reset_token.user_id)
    if user is None or not user.is_active:
        reset_token.used_at = utcnow()
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired reset token",
        )

    user.password_hash = hash_password(body.new_password)
    reset_token.used_at = utcnow()
    await revoke_all_user_sessions(session, user.id)

    await log_auth_event(
        session,
        event_type="password_reset_completed",
        request=request,
        user_id=user.id,
        email=user.email,
    )
    await session.commit()

    return {"status": "ok"}


@router.post("/password-reset/cleanup")
async def cleanup_tokens(
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    from app.services.password_reset_service import cleanup_password_reset_tokens

    deleted = await cleanup_password_reset_tokens(session)
    return {"deleted": deleted}


@router.get("/me", response_model=UserOut)
async def get_me(user: User = Depends(get_current_active_user)) -> UserOut:
    return UserOut.model_validate(user)
