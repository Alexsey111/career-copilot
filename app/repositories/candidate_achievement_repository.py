# app\repositories\candidate_achievement_repository.py

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CandidateAchievement, CandidateProfile


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

    async def get_by_id_for_user(
        self,
        session: AsyncSession,
        *,
        achievement_id: UUID,
        user_id: UUID,
    ) -> CandidateAchievement | None:
        result = await session.execute(
            select(CandidateAchievement)
            .join(CandidateProfile, CandidateAchievement.profile_id == CandidateProfile.id)
            .where(
                CandidateAchievement.id == achievement_id,
                CandidateProfile.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_review(
        self,
        session: AsyncSession,
        *,
        achievement_id: UUID,
        user_id: UUID,
        title: str | None,
        situation: str | None,
        task: str | None,
        action: str | None,
        result: str | None,
        metric_text: str | None,
        fact_status: str,
        evidence_note: str | None,
    ) -> CandidateAchievement | None:
        achievement = await self.get_by_id_for_user(
            session,
            achievement_id=achievement_id,
            user_id=user_id,
        )
        if achievement is None:
            return None

        if title is not None:
            achievement.title = title.strip()

        achievement.situation = self._clean_optional_text(situation)
        achievement.task = self._clean_optional_text(task)
        achievement.action = self._clean_optional_text(action)
        achievement.result = self._clean_optional_text(result)
        achievement.metric_text = self._clean_optional_text(metric_text)
        achievement.evidence_note = self._clean_optional_text(evidence_note)
        achievement.fact_status = fact_status

        await session.flush()
        await session.refresh(achievement)
        return achievement

    def _clean_optional_text(self, value: str | None) -> str | None:
        if value is None:
            return None

        cleaned = value.strip()
        return cleaned or None