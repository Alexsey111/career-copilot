# app/services/oauth_service.py

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import HTTPException, Request, status

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models import User
from app.repositories.user_repository import UserRepository
from app.services.auth_service import issue_tokens, log_auth_event
from app.schemas.auth import TokenResponse


@dataclass
class OAuthUserInfo:
    provider: str
    provider_id: str
    email: str
    email_verified: bool = False
    name: str | None = None
    avatar_url: str | None = None


class OAuthService:
    GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
    GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

    GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
    GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
    GITHUB_USERINFO_URL = "https://api.github.com/user"

    def __init__(self) -> None:
        self.settings = get_settings()

    def get_google_auth_url(self, state: str) -> str:
        params = {
            "client_id": self.settings.oauth_google_client_id,
            "redirect_uri": f"{self.settings.oauth_redirect_base_url}/auth/callback/google",
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline",
        }
        query = "&".join(f"{k}={v}" for k, v in params.items() if v)
        return f"{self.GOOGLE_AUTH_URL}?{query}"

    def get_github_auth_url(self, state: str) -> str:
        params = {
            "client_id": self.settings.oauth_github_client_id,
            "redirect_uri": f"{self.settings.oauth_redirect_base_url}/auth/callback/github",
            "scope": "read:user user:email",
            "state": state,
        }
        query = "&".join(f"{k}={v}" for k, v in params.items() if v)
        return f"{self.GITHUB_AUTH_URL}?{query}"

    async def handle_google_callback(self, code: str, request: Request) -> TokenResponse:
        token_data = await self._exchange_google_code(code)
        user_info = await self._get_google_userinfo(token_data["access_token"])
        return await self._process_oauth_login(user_info, token_data.get("access_token"), request)

    async def handle_github_callback(self, code: str, request: Request) -> TokenResponse:
        token_data = await self._exchange_github_code(code)
        user_info = await self._get_github_userinfo(token_data["access_token"])
        return await self._process_oauth_login(user_info, token_data.get("access_token"), request)

    async def _exchange_google_code(self, code: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                self.GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": self.settings.oauth_google_client_id,
                    "client_secret": self.settings.oauth_google_client_secret,
                    "redirect_uri": f"{self.settings.oauth_redirect_base_url}/auth/callback/google",
                    "grant_type": "authorization_code",
                },
            )
            resp.raise_for_status()
            return resp.json()

    async def _get_google_userinfo(self, access_token: str) -> OAuthUserInfo:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                self.GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            data = resp.json()
            return OAuthUserInfo(
                provider="google",
                provider_id=str(data["id"]),
                email=data["email"],
                email_verified=bool(data.get("verified_email")),
                name=data.get("name"),
                avatar_url=data.get("picture"),
            )

    async def _exchange_github_code(self, code: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                self.GITHUB_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": self.settings.oauth_github_client_id,
                    "client_secret": self.settings.oauth_github_client_secret,
                },
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            return resp.json()

    async def _get_github_userinfo(self, access_token: str) -> OAuthUserInfo:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                self.GITHUB_USERINFO_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()

            emails_resp = await client.get(
                "https://api.github.com/user/emails",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
            )
            verified_primary: str | None = None
            if emails_resp.ok:
                emails = emails_resp.json()
                # Require a primary email that GitHub has verified. Using an
                # unverified email would allow account takeover via a claimed
                # but unconfirmed address.
                for entry in emails:
                    if entry.get("primary") and entry.get("verified"):
                        verified_primary = entry.get("email")
                        break

            if not verified_primary:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Could not retrieve a verified primary email from GitHub",
                )

            return OAuthUserInfo(
                provider="github",
                provider_id=str(data["id"]),
                email=verified_primary,
                email_verified=True,
                name=data.get("name") or data.get("login"),
                avatar_url=data.get("avatar_url"),
            )

    async def _process_oauth_login(
        self,
        user_info: OAuthUserInfo,
        oauth_token: str | None,
        request: Request,
    ) -> TokenResponse:
        if not user_info.email_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OAuth provider did not confirm a verified email",
            )

        async with AsyncSessionLocal() as session:
            repo = UserRepository()

            existing = await repo.get_by_email(session, user_info.email.lower())
            if existing is not None:
                existing.oauth_provider_id = user_info.provider_id
                existing.auth_provider = user_info.provider
                if oauth_token:
                    existing.oauth_access_token = oauth_token
                existing.is_verified = True
                await session.commit()
                await session.refresh(existing)
                await log_auth_event(
                    session,
                    event_type="oauth_login",
                    request=request,
                    user_id=existing.id,
                    email=existing.email,
                    meta={"provider": user_info.provider},
                )
                return await issue_tokens(session, existing, request)

            existing_by_provider = await repo.get_by_oauth_provider_id(
                session,
                provider=user_info.provider,
                provider_id=user_info.provider_id,
            )
            if existing_by_provider is not None:
                if oauth_token:
                    existing_by_provider.oauth_access_token = oauth_token
                await session.commit()
                await session.refresh(existing_by_provider)
                return await issue_tokens(session, existing_by_provider, request)

            user = await repo.create(
                session,
                email=user_info.email.lower(),
                password_hash=None,
                auth_provider=user_info.provider,
            )
            user.oauth_provider_id = user_info.provider_id
            if oauth_token:
                user.oauth_access_token = oauth_token
            user.is_verified = True
            await session.commit()
            await session.refresh(user)
            await log_auth_event(
                session,
                event_type="oauth_register",
                request=request,
                user_id=user.id,
                email=user.email,
                meta={"provider": user_info.provider},
            )
            return await issue_tokens(session, user, request)


_OAUTH_STATE_MAX_AGE_SECONDS = 600


def _state_key() -> bytes:
    return get_settings().jwt_secret.encode("utf-8")


def generate_oauth_state(provider: str) -> str:
    """Build a self-contained, HMAC-signed OAuth ``state`` token.

    The state binds to ``provider`` and an issuance timestamp so the callback
    can verify it statelessly (no server-side store needed): the signature
    proves the value was issued by us, the provider prevents cross-provider
    replay, and the timestamp bounds the validity window.
    """
    nonce = secrets.token_urlsafe(16)
    timestamp = str(int(time.time()))
    payload = f"{provider}:{timestamp}:{nonce}"
    signature = hmac.new(_state_key(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def verify_oauth_state(state: str, provider: str, *, max_age_seconds: int = _OAUTH_STATE_MAX_AGE_SECONDS) -> bool:
    if not state:
        return False
    try:
        payload, signature = state.rsplit(".", 1)
    except ValueError:
        return False
    expected = hmac.new(_state_key(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return False
    parts = payload.split(":")
    if len(parts) != 3:
        return False
    state_provider, timestamp_str, _nonce = parts
    if state_provider != provider:
        return False
    try:
        timestamp = int(timestamp_str)
    except ValueError:
        return False
    if abs(time.time() - timestamp) > max_age_seconds:
        return False
    return True
