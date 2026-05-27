# app\repositories\candidate_achievement_repository.py

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, func, select
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

    async def append_for_profile(
        self,
        session: AsyncSession,
        *,
        profile_id: UUID,
        achievements: Sequence[dict],
    ) -> list[CandidateAchievement]:
        if not achievements:
            return []

        max_order_result = await session.execute(
            select(func.max(CandidateAchievement.order_index)).where(
                CandidateAchievement.profile_id == profile_id
            )
        )
        max_order = max_order_result.scalar()
        next_order = int(max_order) + 1 if max_order is not None else 0

        existing_titles_result = await session.execute(
            select(CandidateAchievement.title).where(
                CandidateAchievement.profile_id == profile_id
            )
        )
        existing_titles = {
            str(title or "").strip().lower()
            for title in existing_titles_result.scalars().all()
            if str(title or "").strip()
        }

        created_items: list[CandidateAchievement] = []
        for offset, item in enumerate(achievements):
            title = str(item.get("title") or "").strip()
            if not title or title.lower() in existing_titles:
                continue

            achievement = CandidateAchievement(
                profile_id=profile_id,
                experience_id=item.get("experience_id"),
                title=title,
                situation=item.get("situation"),
                task=item.get("task"),
                action=item.get("action"),
                result=item.get("result"),
                metric_text=item.get("metric_text"),
                evidence_note=item.get("evidence_note"),
                fact_status=item.get("fact_status", "needs_confirmation"),
                order_index=next_order + offset,
            )
            session.add(achievement)
            created_items.append(achievement)
            existing_titles.add(title.lower())

        await session.flush()
        return created_items

    async def list_for_profile(
        self,
        session: AsyncSession,
        *,
        profile_id: UUID,
    ) -> list[CandidateAchievement]:
        result = await session.execute(
            select(CandidateAchievement)
            .where(CandidateAchievement.profile_id == profile_id)
            .order_by(CandidateAchievement.order_index.asc())
        )
        return list(result.scalars().all())

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
