# app\services\resume_generation_service.py

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


class ResumeGenerationService:
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

    async def generate_resume(
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
        selected_skills, matched_keywords, missing_keywords = self._select_resume_skills(
            raw_skills,
            analysis.keywords_json,
        )

        selected_achievements = self._select_relevant_achievements(
            [a.title for a in profile.achievements],
            analysis.keywords_json,
        )

        fit_summary = self._build_fit_summary(
            vacancy_title=vacancy.title,
            matched_keywords=matched_keywords,
            missing_keywords=missing_keywords,
            analysis_match_score=analysis.match_score,
        )

        summary_bullets = self._build_summary_bullets(
            profile=profile,
            vacancy_title=vacancy.title,
            selected_skills=selected_skills,
            selected_achievements=selected_achievements,
            matched_keywords=matched_keywords,
        )

        experience_items = self._build_experience_items(profile)
        claims_needing_confirmation = self._build_claims_needing_confirmation(
            profile=profile,
            selected_achievements=selected_achievements,
        )
        selection_rationale = self._build_selection_rationale(
            selected_skills=selected_skills,
            matched_keywords=matched_keywords,
            selected_achievements=selected_achievements,
        )
        warnings = self._build_warnings(
            profile=profile,
            selected_achievements=selected_achievements,
            analysis_match_score=analysis.match_score,
            missing_keywords=missing_keywords,
        )

        content_json = {
            "document_kind": "resume",
            "draft_mode": "deterministic_v1_review_ready",
            "candidate": {
                "full_name": profile.full_name,
                "headline": profile.headline,
                "location": profile.location,
                "target_roles": profile.target_roles_json,
            },
            "target_vacancy": {
                "vacancy_id": str(vacancy.id),
                "title": vacancy.title,
                "company": vacancy.company,
                "location": vacancy.location,
            },
            "sections": {
                "fit_summary": fit_summary,
                "summary_bullets": summary_bullets,
                "skills": selected_skills,
                "experience": experience_items,
                "selected_achievements": [
                    {
                        "title": item["title"],
                        "fact_status": item["fact_status"],
                        "reason": item["reason"],
                    }
                    for item in selected_achievements
                ],
                "matched_keywords": matched_keywords,
                "missing_keywords": missing_keywords,
                "claims_needing_confirmation": claims_needing_confirmation,
                "selection_rationale": selection_rationale,
                "warnings": warnings,
            },
        }

        rendered_text = self._render_resume_text(content_json)

        document = await self.document_version_repository.create(
            session,
            user_id=vacancy.user_id,
            vacancy_id=vacancy.id,
            derived_from_id=None,
            document_kind="resume",
            version_label="resume_draft_v2_review_ready",
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

    def _select_resume_skills(
        self,
        raw_skills: list[str],
        keywords: list[str],
    ) -> tuple[list[str], list[str], list[str]]:
        matched_skills: list[str] = []
        matched_keywords: list[str] = []

        for keyword in keywords:
            found_for_keyword = False
            for raw_skill in raw_skills:
                raw_lower = raw_skill.lower()
                keyword_lower = keyword.lower()

                if keyword_lower in raw_lower or raw_lower in keyword_lower:
                    if raw_skill not in matched_skills:
                        matched_skills.append(raw_skill)
                    found_for_keyword = True

            if found_for_keyword and keyword not in matched_keywords:
                matched_keywords.append(keyword)

        remaining = [skill for skill in raw_skills if skill not in matched_skills]
        selected = (matched_skills + remaining)[:12]

        missing_keywords = [keyword for keyword in keywords if keyword not in matched_keywords]
        return selected, matched_keywords, missing_keywords

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
        return selected[:3]

    def _build_fit_summary(
        self,
        *,
        vacancy_title: str,
        matched_keywords: list[str],
        missing_keywords: list[str],
        analysis_match_score: int | None,
    ) -> dict:
        return {
            "target_role": vacancy_title,
            "match_score": analysis_match_score,
            "matched_keyword_count": len(matched_keywords),
            "missing_keyword_count": len(missing_keywords),
        }

    def _build_summary_bullets(
        self,
        *,
        profile,
        vacancy_title: str,
        selected_skills: list[str],
        selected_achievements: list[dict],
        matched_keywords: list[str],
    ) -> list[str]:
        bullets: list[str] = []

        if profile.headline:
            bullets.append(
                f"Targeting {vacancy_title}; current positioning: {profile.headline}."
            )

        if selected_skills:
            bullets.append(
                f"Visible skill base from resume: {', '.join(selected_skills[:6])}."
            )

        if matched_keywords:
            bullets.append(
                f"Current draft already shows overlap with vacancy keywords: {', '.join(matched_keywords[:5])}."
            )

        if selected_achievements:
            bullets.append(
                f"Relevant project direction: {selected_achievements[0]['title']}."
            )

        if profile.experiences:
            current_exp = profile.experiences[0]
            start_part = (
                current_exp.start_date.strftime("%Y") if current_exp.start_date else "unknown start"
            )
            bullets.append(
                f"Current or recent role: {current_exp.role} at {current_exp.company} since {start_part}."
            )

        return bullets[:5]

    def _build_experience_items(self, profile) -> list[dict]:
        items: list[dict] = []

        for exp in profile.experiences[:5]:
            items.append(
                {
                    "company": exp.company,
                    "role": exp.role,
                    "period": self._format_period(exp.start_date, exp.end_date),
                    "description_raw": exp.description_raw,
                }
            )

        return items

    def _build_claims_needing_confirmation(
        self,
        *,
        profile,
        selected_achievements: list[dict],
    ) -> list[dict]:
        claims: list[dict] = []

        for item in selected_achievements:
            claims.append(
                {
                    "type": "achievement",
                    "text": item["title"],
                    "fact_status": item["fact_status"],
                }
            )

        if not profile.full_name:
            claims.append(
                {
                    "type": "profile_field",
                    "text": "full_name missing",
                    "fact_status": "needs_confirmation",
                }
            )

        return claims

    def _build_selection_rationale(
        self,
        *,
        selected_skills: list[str],
        matched_keywords: list[str],
        selected_achievements: list[dict],
    ) -> list[dict]:
        rationale: list[dict] = []

        for skill in selected_skills[:6]:
            reason = "resume_skill"
            if any(keyword.lower() in skill.lower() or skill.lower() in keyword.lower() for keyword in matched_keywords):
                reason = "vacancy_overlap"
            rationale.append({"item": skill, "type": "skill", "reason": reason})

        for ach in selected_achievements:
            rationale.append(
                {
                    "item": ach["title"],
                    "type": "achievement",
                    "reason": ach["reason"],
                }
            )

        return rationale

    def _build_warnings(
        self,
        *,
        profile,
        selected_achievements: list[dict],
        analysis_match_score: int | None,
        missing_keywords: list[str],
    ) -> list[str]:
        warnings: list[str] = []

        if selected_achievements:
            warnings.append(
                "selected achievements remain in needs_confirmation status and require user review"
            )

        if analysis_match_score is not None and analysis_match_score < 40:
            warnings.append(
                "vacancy match score is currently low because structured profile coverage is still limited"
            )

        if missing_keywords:
            warnings.append(
                f"missing or weakly represented vacancy keywords: {', '.join(missing_keywords[:6])}"
            )

        warnings.append("resume draft is ATS-safe plaintext-oriented and not final formatted output")
        return warnings

    def _render_resume_text(self, content_json: dict) -> str:
        candidate = content_json["candidate"]
        vacancy = content_json["target_vacancy"]
        sections = content_json["sections"]

        lines: list[str] = []

        if candidate.get("full_name"):
            lines.append(candidate["full_name"])
        if candidate.get("headline"):
            lines.append(candidate["headline"])
        if candidate.get("location"):
            lines.append(candidate["location"])

        lines.append("")
        lines.append("TARGET ROLE")
        lines.append(vacancy["title"])

        lines.append("")
        lines.append("FIT SUMMARY")
        fit_summary = sections["fit_summary"]
        lines.append(f"- Match score: {fit_summary['match_score']}")
        lines.append(f"- Matched keywords: {fit_summary['matched_keyword_count']}")
        lines.append(f"- Missing keywords: {fit_summary['missing_keyword_count']}")

        lines.append("")
        lines.append("SUMMARY")
        for bullet in sections["summary_bullets"]:
            lines.append(f"- {bullet}")

        lines.append("")
        lines.append("SKILLS")
        for skill in sections["skills"]:
            lines.append(f"- {skill}")

        lines.append("")
        lines.append("EXPERIENCE")
        for item in sections["experience"]:
            lines.append(f"{item['role']} — {item['company']} ({item['period']})")
            if item.get("description_raw"):
                lines.append(f"- {item['description_raw']}")

        lines.append("")
        lines.append("RELEVANT PROJECTS")
        for item in sections["selected_achievements"]:
            lines.append(f"- {item['title']} [{item['fact_status']}]")

        lines.append("")
        lines.append("REVIEW NOTES")
        for warning in sections["warnings"]:
            lines.append(f"- {warning}")

        return "\n".join(lines).strip()

    def _format_period(self, start_date, end_date) -> str:
        start = start_date.strftime("%m.%Y") if start_date else "unknown"
        end = end_date.strftime("%m.%Y") if end_date else "present"
        return f"{start} - {end}"

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
