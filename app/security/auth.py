# app\security\auth.py

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


async def get_current_user_id(
    x_dev_user: str | None = Header(default=None),
) -> str:
    settings = get_settings()

    if settings.dev_auth_enabled:
        if x_dev_user:
            return x_dev_user
        if settings.dev_user_email:
            return settings.dev_user_email

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
    )