# app\schemas\target_track.py

"""Pydantic-схемы target-tracks (Этап 9.D).

Раньше POST/GET работали с сырым ``dict`` без валидации, а ``work_format`` и
``order_index`` молча игнорировались (колонки в модели есть). Здесь —
контрактные ``StrictBaseModel``-схемы + хелперы маппинга с моделью
``CandidateTargetTrack``.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import Field, field_serializer

from app.schemas.base import StrictBaseModel


class TargetTrackBase(StrictBaseModel):
    name: str
    target_roles: list[str] = Field(default_factory=list)
    salary_expectation: Decimal | None = None
    salary_currency: str | None = Field(default=None, max_length=10)
    location_preferences: list[str] = Field(default_factory=list)
    work_format: dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=0, ge=0)
    is_active: bool = True
    notes: str | None = None
    order_index: int = Field(default=0, ge=0)


class TargetTrackCreate(TargetTrackBase):
    name: str = "Untitled track"


class TargetTrackUpdate(StrictBaseModel):
    """Partial PATCH — все поля optional; ``None`` означает «не трогать»."""

    name: str | None = None
    target_roles: list[str] | None = None
    salary_expectation: Decimal | None = None
    salary_currency: str | None = Field(default=None, max_length=10)
    location_preferences: list[str] | None = None
    work_format: dict[str, Any] | None = None
    priority: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    notes: str | None = None
    order_index: int | None = Field(default=None, ge=0)

    def apply_to(self, track) -> None:
        """Применить к модели только non-None поля (partial update)."""
        data = self.model_dump(exclude_unset=True)
        if "name" in data:
            track.name = self.name  # type: ignore[assignment]
        if "target_roles" in data:
            track.target_roles_json = list(self.target_roles or [])
        if "salary_expectation" in data:
            track.salary_expectation = self.salary_expectation
        if "salary_currency" in data:
            track.salary_currency = self.salary_currency
        if "location_preferences" in data:
            track.location_preferences_json = list(self.location_preferences or [])
        if "work_format" in data:
            track.work_format_json = dict(self.work_format or {})
        if "priority" in data:
            track.priority = self.priority  # type: ignore[assignment]
        if "is_active" in data:
            track.is_active = self.is_active  # type: ignore[assignment]
        if "notes" in data:
            track.notes = self.notes
        if "order_index" in data:
            track.order_index = self.order_index  # type: ignore[assignment]


class TargetTrackResponse(TargetTrackBase):
    id: UUID
    profile_id: UUID

    @field_serializer("salary_expectation")
    def _serialize_salary(self, value: Decimal | None) -> float | None:
        if value is None:
            return None
        return float(value)

    @classmethod
    def from_model(cls, track) -> "TargetTrackResponse":
        return cls(
            id=track.id,
            profile_id=track.profile_id,
            name=track.name,
            target_roles=list(track.target_roles_json or []),
            salary_expectation=track.salary_expectation,
            salary_currency=track.salary_currency,
            location_preferences=list(track.location_preferences_json or []),
            work_format=dict(track.work_format_json or {}),
            priority=track.priority,
            is_active=track.is_active,
            notes=track.notes,
            order_index=track.order_index,
        )