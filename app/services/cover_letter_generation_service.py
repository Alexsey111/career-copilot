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
        vacancy = await self.vacancy_repository.get_by_id(
            session,
            vacancy_id,
            user_id=user_id,
        )
        if vacancy is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="vacancy not found",
            )

        analysis = await self.vacancy_analysis_repository.get_latest_for_vacancy(
            session,
            vacancy_id,
            user_id=user_id,
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

        matched_keywords, missing_keywords = self._extract_match_keywords_from_analysis(
            strengths_json=analysis.strengths_json,
            gaps_json=analysis.gaps_json,
        )

        confirmed_achievements = self._get_confirmed_achievements(profile.achievements)

        selected_achievements = self._select_relevant_achievements(
            confirmed_achievements,
            matched_keywords,
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
                "matched_requirements": analysis.strengths_json,
                "gap_requirements": analysis.gaps_json,
                "selected_achievements": [
                    {
                        "title": item["title"],
                        "situation": item.get("situation"),
                        "task": item.get("task"),
                        "action": item.get("action"),
                        "result": item.get("result"),
                        "metric_text": item.get("metric_text"),
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

    def _extract_match_keywords_from_analysis(
        self,
        *,
        strengths_json: list[dict],
        gaps_json: list[dict],
    ) -> tuple[list[str], list[str]]:
        matched_keywords = self._dedupe_preserve_order(
            [
                item.get("keyword", "")
                for item in strengths_json or []
                if item.get("keyword")
            ]
        )
        missing_keywords = self._dedupe_preserve_order(
            [
                item.get("keyword", "")
                for item in gaps_json or []
                if item.get("keyword")
            ]
        )
        return matched_keywords, missing_keywords

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

    def _get_confirmed_achievements(self, achievements) -> list[dict]:
        items: list[dict] = []

        for achievement in achievements or []:
            title = str(getattr(achievement, "title", "") or "").strip()
            fact_status = str(getattr(achievement, "fact_status", "") or "").strip()

            if not title or fact_status != "confirmed":
                continue

            items.append(
                {
                    "title": title,
                    "situation": getattr(achievement, "situation", None),
                    "task": getattr(achievement, "task", None),
                    "action": getattr(achievement, "action", None),
                    "result": getattr(achievement, "result", None),
                    "metric_text": getattr(achievement, "metric_text", None),
                    "fact_status": "confirmed",
                }
            )

        deduped: list[dict] = []
        seen: set[str] = set()

        for item in items:
            normalized = re.sub(r"\s+", " ", item["title"].strip()).lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(item)

        return deduped

    def _get_confirmed_achievement_titles(self, achievements) -> list[str]:
        """
        Backward-compatible helper for existing tests and simple title-only flows.
        Main generation path uses _get_confirmed_achievements().
        """
        return [
            item["title"]
            for item in self._get_confirmed_achievements(achievements)
        ]

    def _select_relevant_achievements(
        self,
        achievements: list[dict] | None = None,
        keywords: list[str] | None = None,
        achievement_titles: list[str] | None = None,
    ) -> list[dict]:
        keywords = keywords or []
        legacy_title_only_mode = achievements is None

        if achievements is None:
            achievements = [
                {
                    "title": title,
                    "fact_status": "confirmed",
                }
                for title in (achievement_titles or [])
            ]

        selected: list[dict] = []

        for achievement in achievements:
            title = str(achievement.get("title") or "").strip()
            if not title:
                continue

            reason = "profile_core"
            title_lower = title.lower()

            if any(keyword.lower() in title_lower for keyword in keywords):
                reason = "keyword_overlap"
            elif "ии" in title_lower or "ai" in title_lower:
                reason = "ai_relevance"
            elif "анализ" in title_lower or "data" in title_lower:
                reason = "analysis_relevance"

            selected_item = {
                "title": title,
                "fact_status": "confirmed",
                "reason": reason,
            }

            if not legacy_title_only_mode:
                selected_item.update(
                    {
                        "situation": achievement.get("situation"),
                        "task": achievement.get("task"),
                        "action": achievement.get("action"),
                        "result": achievement.get("result"),
                        "metric_text": achievement.get("metric_text"),
                    }
                )

            selected.append(selected_item)

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
        company_phrase = f"в {company}" if company else "в вашей команде"
        name_sentence = f"Меня зовут {full_name}. " if full_name else ""

        if headline:
            return (
                "Здравствуйте!\n\n"
                f"{name_sentence}Рассматриваю вакансию {vacancy_title} {company_phrase}. "
                f"Мой текущий профессиональный фокус: {headline}. "
                "Хочу обсудить, где мой опыт и навыки могут быть полезны для задач этой роли."
            )

        return (
            "Здравствуйте!\n\n"
            f"{name_sentence}Рассматриваю вакансию {vacancy_title} {company_phrase}."
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
                "По текущему профилю наиболее подтверждённое пересечение с вакансией: "
                f"{', '.join(matched_keywords[:6])}."
            )

        if selected_achievements:
            achievement_titles = []
            for item in selected_achievements[:2]:
                if item.get("metric_text"):
                    achievement_titles.append(f"{item['title']} ({item['metric_text']})")
                else:
                    achievement_titles.append(item["title"])
            parts.append(
                "Также могу обсудить релевантный проектный опыт: "
                f"{'; '.join(achievement_titles)}."
            )

        if not parts:
            parts.append(
                "Мне интересна эта роль, и я буду рад обсудить, какие задачи команды "
                "могут быть релевантны моему текущему опыту."
            )

        return " ".join(parts)

    def _build_closing(
        self,
        *,
        vacancy_title: str,
        company: str | None,
    ) -> str:
        company_phrase = f"в {company}" if company else "в вашей компании"
        return (
            f"Буду рад обсудить, как мой опыт может быть полезен для позиции "
            f"{vacancy_title} {company_phrase}. Спасибо за внимание к моей кандидатуре."
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
            if item.get("fact_status") != "confirmed"
        ]

    def _build_warnings(
        self,
        *,
        matched_keywords: list[str],
        missing_keywords: list[str],
        selected_achievements: list[dict],
    ) -> list[str]:
        warnings: list[str] = []

        if any(item.get("fact_status") != "confirmed" for item in selected_achievements):
            warnings.append(
                "selected achievements remain in needs_confirmation status and require user review"
            )

        if missing_keywords:
            warnings.append(
                f"profile does not strongly support these vacancy keywords yet: "
                f"{', '.join(missing_keywords[:6])}"
            )

        if not matched_keywords:
            warnings.append(
                "current letter has weak profile-to-vacancy overlap and needs stronger factual grounding"
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
