# app\security\tokens.py

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.core.config import get_settings

settings = get_settings()

def create_access_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)

    payload = {
        "sub": user_id,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(
            (now + timedelta(minutes=settings.jwt_access_token_expire_minutes)).timestamp()
        ),
    }

    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

def decode_access_token(token: str) -> dict[str, Any]:
    payload = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
    )

    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Invalid token type")

    return payload

def generate_refresh_token() -> str:
    return secrets.token_urlsafe(64)

def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def get_refresh_expires() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
