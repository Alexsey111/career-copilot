# app\services\cover_letter_generation_service.py

from __future__ import annotations

import re
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.candidate_profile_repository import CandidateProfileRepository
from app.repositories.document_version_repository import DocumentVersionRepository
from app.repositories.file_extraction_repository import FileExtractionRepository
from app.repositories.vacancy_analysis_repository import VacancyAnalysisRepository
from app.repositories.vacancy_repository import VacancyRepository


class CoverLetterGenerationService:
    def __init__(
        self,
        vacancy_repository: VacancyRepository | None = None,
        vacancy_analysis_repository: VacancyAnalysisRepository | None = None,
        candidate_profile_repository: CandidateProfileRepository | None = None,
        file_extraction_repository: FileExtractionRepository | None = None,
        document_version_repository: DocumentVersionRepository | None = None,
    ) -> None:
        self.vacancy_repository = vacancy_repository or VacancyRepository()
        self.vacancy_analysis_repository = (
            vacancy_analysis_repository or VacancyAnalysisRepository()
        )
        self.candidate_profile_repository = (
            candidate_profile_repository or CandidateProfileRepository()
        )
        self.file_extraction_repository = file_extraction_repository or FileExtractionRepository()
        self.document_version_repository = (
            document_version_repository or DocumentVersionRepository()
        )

    async def generate_cover_letter(
        self,
        session: AsyncSession,
        *,
        vacancy_id: UUID,
        user_id: UUID,
    ):
        vacancy = await self.vacancy_repository.get_by_id(session, vacancy_id)
        if vacancy is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="vacancy not found",
            )

        if vacancy.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="vacancy not found",
            )

        analysis = await self.vacancy_analysis_repository.get_latest_for_vacancy(
            session,
            vacancy_id,
        )
        if analysis is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="vacancy analysis not found; run vacancy analysis first",
            )

        profile = await self.candidate_profile_repository.get_with_related_by_user_id(
            session,
            vacancy.user_id,
        )
        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="candidate profile not found for vacancy user",
            )

        latest_extraction = await self.file_extraction_repository.get_latest_for_user(
            session,
            vacancy.user_id,
        )

        raw_skills = self._extract_skills_from_raw_text(
            latest_extraction.extracted_text if latest_extraction else ""
        )
        matched_keywords, missing_keywords = self._compute_keyword_overlap(
            raw_skills=raw_skills,
            headline=profile.headline,
            target_roles=profile.target_roles_json,
            achievement_titles=[a.title for a in profile.achievements],
            keywords=analysis.keywords_json,
        )

        selected_achievements = self._select_relevant_achievements(
            [a.title for a in profile.achievements],
            analysis.keywords_json,
        )

        opening = self._build_opening(
            full_name=profile.full_name,
            vacancy_title=vacancy.title,
            company=vacancy.company,
            headline=profile.headline,
        )
        relevance_paragraph = self._build_relevance_paragraph(
            matched_keywords=matched_keywords,
            selected_achievements=selected_achievements,
        )
        closing = self._build_closing(
            vacancy_title=vacancy.title,
            company=vacancy.company,
        )
        claims_needing_confirmation = self._build_claims_needing_confirmation(
            selected_achievements=selected_achievements,
        )
        warnings = self._build_warnings(
            matched_keywords=matched_keywords,
            missing_keywords=missing_keywords,
            selected_achievements=selected_achievements,
        )

        content_json = {
            "document_kind": "cover_letter",
            "draft_mode": "deterministic_v1_review_ready",
            "candidate": {
                "full_name": profile.full_name,
                "headline": profile.headline,
                "location": profile.location,
            },
            "target_vacancy": {
                "vacancy_id": str(vacancy.id),
                "title": vacancy.title,
                "company": vacancy.company,
                "location": vacancy.location,
            },
            "sections": {
                "opening": opening,
                "relevance_paragraph": relevance_paragraph,
                "closing": closing,
                "matched_keywords": matched_keywords,
                "missing_keywords": missing_keywords,
                "selected_achievements": [
                    {
                        "title": item["title"],
                        "fact_status": item["fact_status"],
                        "reason": item["reason"],
                    }
                    for item in selected_achievements
                ],
                "claims_needing_confirmation": claims_needing_confirmation,
                "warnings": warnings,
            },
        }

        rendered_text = self._render_cover_letter(content_json)

        document = await self.document_version_repository.create(
            session,
            user_id=vacancy.user_id,
            vacancy_id=vacancy.id,
            derived_from_id=None,
            document_kind="cover_letter",
            version_label="cover_letter_draft_v1",
            review_status="draft",
            is_active=False,
            content_json=content_json,
            rendered_text=rendered_text,
        )

        await session.commit()
        await session.refresh(document)
        return document

    def _extract_skills_from_raw_text(self, text: str) -> list[str]:
        if not text:
            return []

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        capture = False
        section_lines: list[str] = []

        for line in lines:
            normalized = line.upper()

            if normalized == "ПРОФЕССИОНАЛЬНЫЕ НАВЫКИ":
                capture = True
                continue

            if capture and normalized in {
                "ЖЕЛАЕМАЯ ДОЛЖНОСТЬ",
                "ОПЫТ РАБОТЫ",
                "ОБРАЗОВАНИЕ",
            }:
                break

            if capture:
                section_lines.append(line)

        if not section_lines:
            return []

        joined = " ".join(section_lines)
        parts = [part.strip(" .") for part in joined.split(",") if part.strip()]
        return self._dedupe_preserve_order(parts)

    def _compute_keyword_overlap(
        self,
        *,
        raw_skills: list[str],
        headline: str | None,
        target_roles: list[str],
        achievement_titles: list[str],
        keywords: list[str],
    ) -> tuple[list[str], list[str]]:
        corpus_parts: list[str] = []
        corpus_parts.extend(raw_skills)
        corpus_parts.extend(target_roles)
        corpus_parts.extend(achievement_titles)
        if headline:
            corpus_parts.append(headline)

        corpus = "\n".join(corpus_parts).lower()

        matched: list[str] = []
        missing: list[str] = []

        for keyword in keywords:
            if keyword.lower() in corpus:
                matched.append(keyword)
            else:
                missing.append(keyword)

        return matched, missing

    def _select_relevant_achievements(
        self,
        achievement_titles: list[str],
        keywords: list[str],
    ) -> list[dict]:
        selected: list[dict] = []

        for title in achievement_titles:
            reason = "profile_core"
            title_lower = title.lower()

            if any(keyword.lower() in title_lower for keyword in keywords):
                reason = "keyword_overlap"
            elif "ии" in title_lower or "ai" in title_lower:
                reason = "ai_relevance"
            elif "анализ" in title_lower or "data" in title_lower:
                reason = "analysis_relevance"

            selected.append(
                {
                    "title": title,
                    "fact_status": "needs_confirmation",
                    "reason": reason,
                }
            )

        selected = sorted(
            selected,
            key=lambda item: (
                0 if item["reason"] == "keyword_overlap" else
                1 if item["reason"] == "ai_relevance" else
                2 if item["reason"] == "analysis_relevance" else
                3
            ),
        )
        return selected[:2]

    def _build_opening(
        self,
        *,
        full_name: str | None,
        vacancy_title: str,
        company: str | None,
        headline: str | None,
    ) -> str:
        company_part = company or "your team"

        if headline:
            return (
                f"Dear hiring team,\n\n"
                f"I am applying for the {vacancy_title} role at {company_part}. "
                f"My current positioning is {headline}, and I am interested in roles where I can "
                f"apply AI, prompting, and data-oriented work in a practical product context."
            )

        name_part = full_name or "I"
        return (
            f"Dear hiring team,\n\n"
            f"{name_part} am applying for the {vacancy_title} role at {company_part}."
        )

    def _build_relevance_paragraph(
        self,
        *,
        matched_keywords: list[str],
        selected_achievements: list[dict],
    ) -> str:
        parts: list[str] = []

        if matched_keywords:
            parts.append(
                f"My resume already shows overlap with the vacancy requirements in areas such as "
                f"{', '.join(matched_keywords[:6])}."
            )

        if selected_achievements:
            parts.append(
                f"I also have project directions relevant to this role, including "
                f"{selected_achievements[0]['title']}"
                + (
                    f" and {selected_achievements[1]['title']}."
                    if len(selected_achievements) > 1
                    else "."
                )
            )

        if not parts:
            parts.append(
                "I am particularly interested in this role because it combines practical AI work "
                "with clear product-facing requirements."
            )

        return " ".join(parts)

    def _build_closing(
        self,
        *,
        vacancy_title: str,
        company: str | None,
    ) -> str:
        company_part = company or "your company"
        return (
            f"I would be glad to discuss how my background and project experience can be adapted "
            f"to the {vacancy_title} role at {company_part}. Thank you for your consideration."
        )

    def _build_claims_needing_confirmation(
        self,
        *,
        selected_achievements: list[dict],
    ) -> list[dict]:
        return [
            {
                "type": "achievement",
                "text": item["title"],
                "fact_status": item["fact_status"],
            }
            for item in selected_achievements
        ]

    def _build_warnings(
        self,
        *,
        matched_keywords: list[str],
        missing_keywords: list[str],
        selected_achievements: list[dict],
    ) -> list[str]:
        warnings: list[str] = []

        if selected_achievements:
            warnings.append(
                "selected achievements remain in needs_confirmation status and require user review"
            )

        if missing_keywords:
            warnings.append(
                f"letter does not yet address some vacancy keywords strongly: {', '.join(missing_keywords[:6])}"
            )

        if not matched_keywords:
            warnings.append(
                "current letter has weak keyword overlap and may need stronger tailoring"
            )

        warnings.append("cover letter draft should be reviewed before sending")
        return warnings

    def _render_cover_letter(self, content_json: dict) -> str:
        sections = content_json["sections"]

        return (
            f"{sections['opening']}\n\n"
            f"{sections['relevance_paragraph']}\n\n"
            f"{sections['closing']}"
        ).strip()

    def _dedupe_preserve_order(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []

        for value in values:
            normalized = re.sub(r"\s+", " ", value.strip()).lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(value.strip())

        return result
