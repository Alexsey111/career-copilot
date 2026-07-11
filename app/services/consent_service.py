# app/services/consent_service.py

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import UserConsent


CONSENT_TYPES = {
    "data_processing": {
        "description": "Согласие на обработку персональных данных",
        "required": True,
        "version": "1.0",
    },
    "ai_generation": {
        "description": "Согласие на использование AI для генерации документов",
        "required": True,
        "version": "1.0",
    },
    "profile_storage": {
        "description": "Согласие на хранение профиля и данных",
        "required": True,
        "version": "1.0",
    },
    "analytics_tracking": {
        "description": "Согласие на сбор аналитики поиска работы",
        "required": False,
        "version": "1.0",
    },
    "third_party_sharing": {
        "description": "Согласие на передачу данных третьим лицам",
        "required": False,
        "version": "1.0",
    },
}


class ConsentService:
    async def get_user_consents(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
    ) -> list[dict[str, Any]]:
        stmt = select(UserConsent).where(UserConsent.user_id == user_id)
        result = await session.execute(stmt)
        consents = result.scalars().all()

        consent_map = {
            c.consent_type: c for c in consents
        }

        return [
            {
                "consent_type": ct,
                "description": info["description"],
                "required": info["required"],
                "version": info["version"],
                "granted": consent_map[ct].granted if ct in consent_map else False,
                "granted_at": consent_map[ct].granted_at.isoformat() if ct in consent_map and consent_map[ct].granted_at else None,
                "revoked_at": consent_map[ct].revoked_at.isoformat() if ct in consent_map and consent_map[ct].revoked_at else None,
            }
            for ct, info in CONSENT_TYPES.items()
        ]

    async def grant_consent(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        consent_type: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        if consent_type not in CONSENT_TYPES:
            raise ValueError(f"Unknown consent type: {consent_type}")

        info = CONSENT_TYPES[consent_type]
        now = datetime.now(timezone.utc)

        stmt = select(UserConsent).where(
            UserConsent.user_id == user_id,
            UserConsent.consent_type == consent_type,
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is not None:
            existing.granted = True
            existing.granted_at = now
            existing.revoked_at = None
            existing.version = info["version"]
            if ip_address:
                existing.ip_address = ip_address
            if user_agent:
                existing.user_agent = user_agent
        else:
            consent = UserConsent(
                user_id=user_id,
                consent_type=consent_type,
                granted=True,
                version=info["version"],
                granted_at=now,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            session.add(consent)

        await session.flush()

        return {
            "consent_type": consent_type,
            "granted": True,
            "granted_at": now.isoformat(),
            "version": info["version"],
        }

    async def revoke_consent(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        consent_type: str,
    ) -> dict[str, Any]:
        if consent_type not in CONSENT_TYPES:
            raise ValueError(f"Unknown consent type: {consent_type}")

        stmt = select(UserConsent).where(
            UserConsent.user_id == user_id,
            UserConsent.consent_type == consent_type,
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is None or not existing.granted:
            return {
                "consent_type": consent_type,
                "granted": False,
                "message": "Consent was not granted",
            }

        now = datetime.now(timezone.utc)
        existing.granted = False
        existing.revoked_at = now
        await session.flush()

        return {
            "consent_type": consent_type,
            "granted": False,
            "revoked_at": now.isoformat(),
        }

    async def check_consent(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        consent_type: str,
    ) -> bool:
        if consent_type not in CONSENT_TYPES:
            return False

        info = CONSENT_TYPES[consent_type]
        if not info["required"]:
            return True

        stmt = select(UserConsent).where(
            UserConsent.user_id == user_id,
            UserConsent.consent_type == consent_type,
            UserConsent.granted == True,
        )
        result = await session.execute(stmt)
        consent = result.scalar_one_or_none()
        return consent is not None

    async def check_required_consents(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
    ) -> dict[str, Any]:
        all_consents = await self.get_user_consents(session, user_id=user_id)

        missing_required = [
            c for c in all_consents
            if c["required"] and not c["granted"]
        ]

        return {
            "all_granted": len(missing_required) == 0,
            "missing_required": [c["consent_type"] for c in missing_required],
            "consents": all_consents,
        }
