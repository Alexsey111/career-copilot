from datetime import datetime, timezone, timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PasswordResetToken


async def cleanup_password_reset_tokens(session: AsyncSession) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=1)

    result = await session.execute(
        delete(PasswordResetToken).where(
            (PasswordResetToken.used_at.is_not(None))
            | (PasswordResetToken.expires_at < cutoff)
        )
    )

    await session.commit()
    return result.rowcount or 0