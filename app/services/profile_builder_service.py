# app\services\profile_builder_service.py

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CandidateProfile, CandidateExperience, User


class ProfileBuilderService:
    async def build_from_resume_text(
        self,
        session: AsyncSession,
        *,
        user: User,
        text: str,
    ) -> CandidateProfile:
        """
        MVP: extremely naive parser
        """

        # 1. Create profile if not exists
        profile = user.profile
        if not profile:
            profile = CandidateProfile(
                user_id=user.id,
                full_name=None,
                headline=None,
                summary=None,
                target_roles_json=[],
                work_format_preferences_json={},
            )
            session.add(profile)
            await session.flush()

        # 2. VERY SIMPLE extraction (MVP)
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        # naive heuristics
        full_name = lines[0] if lines else None
        profile.full_name = full_name

        # find skills section
        skills = []
        for line in lines:
            if "Python" in line or "SQL" in line:
                skills.append(line)

        if skills:
            profile.summary = " | ".join(skills)

        # 3. create fake experience (MVP)
        exp = CandidateExperience(
            profile_id=profile.id,
            company="Unknown",
            role="Unknown",
            description_raw=text[:500],
            order_index=0,
        )
        session.add(exp)

        await session.commit()
        await session.refresh(profile)

        return profile