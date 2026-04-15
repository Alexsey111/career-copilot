# app\repositories\candidate_achievement_repository.py

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CandidateAchievement


class CandidateAchievementRepository:
    async def replace_for_profile(
        self,
        session: AsyncSession,
        *,
        profile_id: UUID,
        achievements: Sequence[dict],
    ) -> list[CandidateAchievement]:
        await session.execute(
            delete(CandidateAchievement).where(CandidateAchievement.profile_id == profile_id)
        )

        created_items: list[CandidateAchievement] = []

        for idx, item in enumerate(achievements):
            achievement = CandidateAchievement(
                profile_id=profile_id,
                experience_id=item.get("experience_id"),
                title=item["title"],
                situation=item.get("situation"),
                task=item.get("task"),
                action=item.get("action"),
                result=item.get("result"),
                metric_text=item.get("metric_text"),
                evidence_note=item.get("evidence_note"),
                fact_status=item.get("fact_status", "needs_confirmation"),
                order_index=idx,
            )
            session.add(achievement)
            created_items.append(achievement)

        await session.flush()
        return created_items