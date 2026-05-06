# app\services\cover_letter_generation_service.py

from __future__ import annotations

import re
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.candidate_profile_repository import CandidateProfileRepository
from app.repositories.document_version_repository import DocumentVersionRepository
from app.repositories.file_extraction_repository import FileExtractionRepository
from app.repositories.vacancy_analysis_repository import VacancyAnalysisRepository
from app.repositories.vacancy_repository import VacancyRepository
from app.schemas.json_contracts import CoverLetterContent


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
        use_ai_enhancement: bool = False,
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

        # Собираем профильные навыки для контекста
        profile_skills = self._extract_skills_from_profile(profile)

        opening = self._build_opening(
            full_name=profile.full_name,
            vacancy_title=vacancy.title,
            company=vacancy.company,
            headline=profile.headline,
        )
        relevance_paragraph = self._build_relevance_paragraph(
            matched_keywords=matched_keywords,
            selected_achievements=selected_achievements,
            missing_keywords=missing_keywords,
            profile_skills=profile_skills,
            vacancy_title=vacancy.title,
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

        # Опциональный AI-усиленный шаг для всего письма
        rendered_text = self._render_cover_letter(
            {
                "sections": {
                    "opening": opening,
                    "relevance_paragraph": relevance_paragraph,
                    "closing": closing,
                    "warnings": warnings,
                }
            }
        )

        if use_ai_enhancement and self.ai_orchestrator:
            from app.ai.use_cases.cover_letter_enhance import enhance_cover_letter

            enhanced = await enhance_cover_letter(
                self.ai_orchestrator,
                session,
                user_id=user_id,
                draft_text=rendered_text,
                language="ru",
            )

            enhanced_text = enhanced["result"]["enhanced_text"]

            if not self._is_safe_enhancement(rendered_text, enhanced_text):
                rendered_text = rendered_text  # fallback, не меняем
            else:
                rendered_text = enhanced_text

        content_json = {
            "document_kind": "cover_letter",
            "draft_mode": "deterministic_v1_review_ready" if not use_ai_enhancement else "ai_enhanced_v1",
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
                        "id": item.get("id"),
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
            "meta": {
                "source": "hybrid" if use_ai_enhancement else "extracted",
                "based_on_achievements": [
                    item.get("id") for item in selected_achievements if item.get("id")
                ],
                "based_on_analysis_id": str(analysis.id),
                "confidence": self._compute_confidence(
                    selected_achievements=selected_achievements,
                    missing_keywords=missing_keywords,
                ),
                "generation_prompt_version": (
                    "cover_letter_v1" if use_ai_enhancement else None
                ),
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "warnings": [],
            },
        }

        # Валидация JSON-контракта перед сохранением (type-specific)
        validated_content = CoverLetterContent.model_validate(content_json)
        content_json = validated_content.model_dump()

        document = await self.document_version_repository.create(
            session,
            user_id=vacancy.user_id,
            vacancy_id=vacancy.id,
            derived_from_id=None,
            analysis_id=analysis.id,
            document_kind="cover_letter",
            version_label="cover_letter_draft_v1" if not use_ai_enhancement else "cover_letter_ai_enhanced_v1",
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

    def _split_skill_text(self, text: str) -> list[str]:
        if not text:
            return []
        parts = re.split(r"[,\n;]+", text)
        cleaned = [
            re.sub(r"\s+", " ", part.strip(" .;-–—•"))
            for part in parts
            if part.strip(" .;-–—•")
        ]
        return self._dedupe_preserve_order(cleaned)

    def _extract_skills_from_profile(self, profile) -> list[str]:
        """Извлекает список навыков из профиля для контекста gap-mitigation"""
        skills: list[str] = []
        # Из headline и summary
        if profile.headline:
            skills.extend(self._split_skill_text(profile.headline))
        if profile.summary:
            skills.extend(self._split_skill_text(profile.summary))
        # Из опыта работы
        for exp in profile.experiences or []:
            if exp.description_raw:
                skills.extend(self._extract_skills_from_raw_text(exp.description_raw))
        # Из достижений
        for ach in profile.achievements or []:
            if ach.action:
                skills.extend(self._split_skill_text(ach.action))
            if ach.result:
                skills.extend(self._split_skill_text(ach.result))
        return self._dedupe_preserve_order(skills)

    def _get_confirmed_achievements(self, achievements) -> list[dict]:
        items: list[dict] = []

        for achievement in achievements or []:
            title = str(getattr(achievement, "title", "") or "").strip()
            fact_status = str(getattr(achievement, "fact_status", "") or "").strip()

            if not title or fact_status != "confirmed":
                continue

            items.append(
                {
                    "id": str(getattr(achievement, "id", "")),
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
        missing_keywords: list[str],
        profile_skills: list[str],
        vacancy_title: str,
    ) -> str:
        parts: list[str] = []

        # 1. Сильные совпадения
        if matched_keywords:
            parts.append(
                "По текущему профилю наиболее подтверждённое пересечение с вакансией: "
                f"{', '.join(matched_keywords[:6])}."
            )

        # 2. Релевантный проектный опыт
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

        # 3. Gap-mitigation (новый блок)
        gap_paragraph = self._build_gap_mitigation_paragraph(
            missing_keywords=missing_keywords,
            profile_skills=profile_skills,
            vacancy_title=vacancy_title,
        )
        if gap_paragraph:
            parts.append(gap_paragraph)

        # Fallback, если ничего не добавилось
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

    def _build_gap_mitigation_paragraph(
        self,
        *,
        missing_keywords: list[str],
        profile_skills: list[str],
        vacancy_title: str,
    ) -> str | None:
        """
        Генерирует абзац, который проактивно закрывает критичные пробелы.
        Возвращает None, если пробелов нет или они не критичны.
        """
        if not missing_keywords:
            return None

        # Берём топ-3 самых критичных gap'а (must-have из анализа)
        critical_gaps = [kw for kw in missing_keywords[:3] if kw]
        if not critical_gaps:
            return None

        # Карта "мягких" формулировок для частых технологий
        bridge_phrases = {
            "FastAPI": "имею опыт работы с async-фреймворками (Starlette, aiohttp) и готов быстро адаптироваться под FastAPI",
            "PostgreSQL": "работаю с реляционными СУБД и знаком с принципами оптимизации запросов",
            "Docker": "использую контейнеризацию в локальной разработке и готов углубить практику в CI/CD",
            "Redis": "понимаю принципы кэширования и работы с in-memory хранилищами",
            "CI/CD": "настраивал базовые пайплайны деплоя и готов активно развивать эту компетенцию",
            "Kubernetes": "изучаю оркестрацию контейнеров и готов применять знания на практике",
            "AWS": "имею опыт работы с облачными сервисами и готов освоить специфичные для роли инструменты",
        }

        mitigations: list[str] = []
        for gap in critical_gaps:
            # Пробуем найти готовую формулировку
            phrase = bridge_phrases.get(gap)
            if phrase:
                mitigations.append(phrase)
            else:
                # Fallback: нейтральная, но проактивная формулировка
                mitigations.append(f"активно изучаю {gap} в рамках подготовки к роли {vacancy_title}")

        if not mitigations:
            return None

        return (
            "Отмечу, что " + "; ".join(mitigations) + ". "
            "Готов оперативно закрыть оставшиеся зоны в процессе онбординга."
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

    def _compute_confidence(
        self,
        *,
        selected_achievements: list[dict],
        missing_keywords: list[str],
    ) -> float:
        """Вычисляет confidence score на основе качества исходных данных."""
        if not selected_achievements:
            return 0.3

        confirmed_count = sum(
            1 for item in selected_achievements
            if item.get("fact_status") == "confirmed"
        )
        confirmed_ratio = confirmed_count / len(selected_achievements)

        base_score = 0.4 + (confirmed_ratio * 0.6)

        if missing_keywords:
            penalty = min(len(missing_keywords) * 0.05, 0.3)
            base_score -= penalty

        return round(max(0.1, min(1.0, base_score)), 2)

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

    def _build_draft(
        self,
        *,
        vacancy_title: str,
        company: str,
        strengths: list[str],
        gaps: list[str],
        achievements: list[str],
    ) -> str:
        parts = []

        # Intro
        parts.append(
            f"I am applying for the {vacancy_title} role at {company}."
        )

        # Strengths
        if strengths:
            parts.append(
                "My experience aligns well with your requirements, including: "
                + ", ".join(strengths[:3])
            )

        # Achievements
        if achievements:
            parts.append(
                "Relevant accomplishments include: "
                + "; ".join(achievements[:2])
            )

        # Gaps (ключевой блок)
        if gaps:
            parts.append(
                "While I am still developing experience in "
                + ", ".join(gaps[:2])
                + ", I have been actively working to strengthen these areas."
            )

        # Closing
        parts.append("I would welcome the opportunity to contribute to your team.")

        return "\n\n".join(parts)

    def _word_count(self, text: str) -> int:
        return len(text.split())

    def _is_safe_enhancement(self, original: str, enhanced: str) -> bool:
        orig_words = self._word_count(original)
        enh_words = self._word_count(enhanced)

        # 1. защита от пустого / деградации
        if enh_words == 0:
            return False

        # 2. слишком сильное сжатие
        if enh_words < orig_words * 0.5:
            return False

        # 3. слишком сильное раздувание (более мягкое)
        if enh_words > orig_words * 2.5:
            return False

        # 4. ключевые слова не должны исчезнуть
        for word in original.split():
            # Убираем пунктуацию для сравнения
            clean_word = re.sub(r'[^\w]', '', word).lower()
            if len(clean_word) > 4 and clean_word not in enhanced.lower():
                return False

        return True

    async def enhance_cover_letter_with_ai(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        draft_text: str,
        language: str = "ru",
    ) -> str:
        if not self.ai_orchestrator:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="AI orchestrator not configured",
            )

        from app.ai.use_cases.cover_letter_enhance import enhance_cover_letter

        result = await enhance_cover_letter(
            self.ai_orchestrator,
            session,
            user_id=user_id,
            draft_text=draft_text,
            language=language,
        )

        enhanced = result["result"]["enhanced_text"]

        if not self._is_safe_enhancement(draft_text, enhanced):
            return draft_text

        return enhanced
