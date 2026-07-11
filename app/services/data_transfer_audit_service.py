# app/services/data_transfer_audit_service.py

"""Аудит передачи персональных данных внешним обработчикам (ФЗ-152 ст.18/19).

Каждая передача ПДн стороннему AI-обработчику фиксируется в таблице
``data_transfer_events``: кто передал, кому (провайдер/модель), какая
категория ПДн, основание (согласие), цель (workflow) и когда.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DataTransferEvent


class DataTransferAuditService:
    async def log(
        self,
        session: AsyncSession,
        *,
        user_id: Any,
        recipient: str,
        purpose: str,
        data_categories: list[str] | None = None,
        legal_basis: str = "consent",
        consent_type: str = "ai_generation",
        model_name: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> DataTransferEvent:
        event = DataTransferEvent(
            user_id=user_id,
            recipient=recipient,
            purpose=purpose,
            data_categories=data_categories or ["personal_data"],
            legal_basis=legal_basis,
            consent_type=consent_type,
            model_name=model_name,
            ip_address=ip_address,
            user_agent=user_agent,
            meta_json=meta or {},
        )
        session.add(event)
        await session.flush()
        return event