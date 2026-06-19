from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from app.domain.evidence_alignment import humanize_experience_phrase, score_alignment_item
from app.domain.requirement_normalization import classify_requirement_phrase, requirement_match_key
from app.domain.text_normalization import (
    clean_vacancy_title,
    dedupe_subsumed_phrases,
    make_user_facing_evidence_phrase,
)
from app.services.text_polish.humanizer import (
    join_cover_letter_phrases,
    join_experience_phrases,
)
from app.services.text_polish.achievement_verbalizer import (
    AchievementStyle,
    verbalize_achievement_phrase,
)


SOFT_COMPETENCIES = {
    "аккуратность",
    "внимательность",
    "ответственность",
    "исполнительность",
    "коммуникабельность",
}

LOW_SIGNAL_GAP_TOPICS = {
    "пользователь пк",
    "скорость",
    "компетентность",
    "профильное законодательство",
    "профильного законодательства",
    "знание профильного законодательства",
    "нормотворческая деятельность",
}


def build_gap_mitigation_paragraph(
    *,
    vacancy_fit_narrative: dict[str, Any],
    profile_skills: list[str],
    vacancy_title: str,
) -> str | None:
    clean_vacancy_title(vacancy_title)
    gap_items = vacancy_fit_narrative.get("critical_gaps") or []
    if not gap_items:
        return None

    matched_labels = {
        requirement_match_key(str(item.get("label") or ""))
        for item in (vacancy_fit_narrative.get("matched_strengths") or [])
        if requirement_match_key(str(item.get("label") or ""))
    }
    profile_skill_keys = {
        requirement_match_key(str(skill or ""))
        for skill in profile_skills
        if requirement_match_key(str(skill or ""))
    }

    gap_items = dedupe_gap_keywords(
        [
            str(item.get("label") or "").strip()
            for item in gap_items
            if str(item.get("label") or "").strip()
            and requirement_match_key(str(item.get("label") or ""))
            not in matched_labels
            and not gap_is_supported_by_profile_skills(
                str(item.get("label") or ""),
                profile_skill_keys,
            )
            and gap_mitigation_allowed(item)
            and str(item.get("label") or "").strip().lower() not in SOFT_COMPETENCIES
            and str(item.get("label") or "").strip().lower() not in LOW_SIGNAL_GAP_TOPICS
        ]
    )
    gap_items = sorted(
        gap_items,
        key=score_gap_for_cover_letter,
        reverse=True,
    )
    critical_gaps = gap_items[:2]

    if not critical_gaps:
        return None

    gap_focus = render_gap_topics(critical_gaps)
    if not gap_focus:
        return None

    return (
        "Отдельно готов обсудить план быстрого погружения: "
        f"{gap_focus}."
    )


def gap_is_supported_by_profile_skills(label: str, profile_skill_keys: set[str]) -> bool:
    gap_key = requirement_match_key(label)
    if not gap_key or not profile_skill_keys:
        return False
    if gap_key in profile_skill_keys:
        return True
    return any(skill_key and skill_key in gap_key for skill_key in profile_skill_keys)


def cover_letter_requirement_focus(
    *,
    matched_keywords: list[str],
    vacancy_title: str,
) -> str:
    vacancy_title = clean_vacancy_title(vacancy_title)
    labels: list[str] = []
    corpus = " ".join([vacancy_title, *matched_keywords]).lower()

    if "python" in corpus:
        labels.append("Python и backend/API-разработки")
    elif any(marker in corpus for marker in ("fastapi", "backend", "api")):
        labels.append("backend/API-разработки")
    if any(marker in corpus for marker in ("automation", "workflow", "no-code", "nocode")):
        labels.append("автоматизации workflow")
    if any(marker in corpus for marker in ("prompt", "llm", "chatgpt", "openai")):
        labels.append("AI-assisted процессов")
    if any(marker in corpus for marker in ("computer vision", "monitoring", "quality control")):
        labels.append("прикладного AI/CV мониторинга")

    return ", ".join(dedupe_preserve_order(labels)[:2])


def cover_letter_experience_value(
    *,
    vacancy_title: str,
    matched_keywords: list[str],
    candidate_experiences: list[Any] | None,
    is_supply_management_context: Callable[..., bool],
    compress_experience_phrases: Callable[[list[str]], list[str]],
) -> str:
    if not candidate_experiences:
        return ""

    vacancy_title = clean_vacancy_title(vacancy_title)
    corpus = " ".join([vacancy_title, *matched_keywords]).lower()

    priority_markers = (
        "команд",
        "управлен",
        "обуч",
        "контрол",
        "отчет",
        "отчёт",
        "мерчандайз",
        "супервайзер",
        "маршрут",
        "аудит",
        "первич",
        "бухгалтер",
        "акт",
        "счет",
        "счёт",
        "сверк",
        "плат",
        "склад",
        "приемк",
        "приёмк",
        "отгруз",
        "комплектац",
        "достав",
        "перевоз",
        "снабжен",
        "закуп",
        "поставщик",
        "договор",
        "претензи",
        "мтс",
        "бюджет",
        "запас",
    )
    supply_management_context = is_supply_management_context(
        vacancy_title=vacancy_title,
        matched_keywords=matched_keywords,
        phrases=[],
    )
    supply_management_markers = (
        "снабжен",
        "закуп",
        "поставщик",
        "поставк",
        "договор",
        "претензи",
        "мтс",
        "бюджет",
        "запас",
        "склад",
        "логист",
        "переговор",
        "контрол",
    )

    bullets: list[str] = []
    for exp in candidate_experiences[:3]:
        description = str(getattr(exp, "description_raw", "") or "")
        for part in re.split(r"\s+-\s+|[\n;•]+", description):
            cleaned = re.sub(r"\s+", " ", part).strip(" .;-–—•")
            if not cleaned:
                continue

            normalized = cleaned.lower()
            if any(marker in corpus and marker in normalized for marker in priority_markers):
                bullets.append(cleaned)
                continue
            if supply_management_context and any(
                marker in normalized for marker in supply_management_markers
            ):
                bullets.append(cleaned)

    bullets = dedupe_preserve_order(bullets)
    if not bullets:
        for exp in candidate_experiences[:3]:
            description = str(getattr(exp, "description_raw", "") or "")
            polished = humanize_experience_phrase(description)
            if polished != re.sub(r"\s+", " ", description).strip(" .;-–—•"):
                bullets.extend(
                    part.strip()
                    for part in polished.split(",")
                    if part.strip()
                )
        bullets = dedupe_preserve_order(bullets)
    if not bullets:
        return ""

    compressed = compress_experience_phrases(bullets)
    if is_supply_management_context(
        vacancy_title=vacancy_title,
        matched_keywords=matched_keywords,
        phrases=compressed,
    ):
        return join_cover_letter_phrases(compressed[:5])
    return join_experience_phrases(compressed[:3])


def render_gap_topics(critical_gaps: list[str]) -> str | None:
    topics = [
        gap_topic_label(gap)
        for gap in critical_gaps[:2]
        if str(gap or "").strip(" .;-–—•")
    ]
    topics = [topic for topic in topics if topic]
    topics = dedupe_preserve_order(topics)
    if not topics:
        return None
    if len(topics) == 1:
        return topics[0]
    return f"{topics[0]} и {topics[1]}"


def gap_topic_label(gap: str) -> str:
    normalized = re.sub(r"\s+", " ", str(gap or "")).strip(" .;-–—•")
    lowered = normalized.lower()
    if lowered in {"automation", "automation tooling"}:
        return "автоматизация тестирования"
    return normalized


def gap_mitigation_allowed(item: dict[str, Any]) -> bool:
    classification = str(item.get("classification") or "").strip().lower()
    if not classification:
        classification = classify_requirement_phrase(
            str(item.get("label") or "")
        )
    return classification not in {"education", "certification"}


def score_gap_for_cover_letter(label: str) -> int:
    lowered = str(label or "").lower()
    if "bim" in lowered:
        return 100
    if "экспертиз" in lowered:
        return 90
    if "объект" in lowered:
        return 70
    if "деловая коммуникация" in lowered:
        return 10
    return 30


def to_gap_case(gap: str) -> str:
    normalized = re.sub(r"\s+", " ", str(gap or "")).strip(" .;-–—•")
    lowered = normalized.lower()
    if lowered == "мерчандайзинг":
        return "мерчандайзинге"
    if lowered == "полевой аудит торговых точек":
        return "полевом аудите торговых точек"
    if lowered == "профильное законодательство":
        return "профильном законодательстве"
    if lowered == "нормотворческая деятельность":
        return "нормотворческой деятельности"
    if lowered in {"automation", "automation tooling"}:
        return "автоматизации тестирования"
    if lowered == "bim-процессы":
        return "BIM-процессах"
    if lowered == "взаимодействие с экспертизой":
        return "взаимодействии с экспертизой"
    if lowered == "ведение проектной документации":
        return "ведении проектной документации"
    if lowered == "деловая коммуникация":
        return "деловой коммуникации"
    return normalized


def dedupe_gap_keywords(keywords: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for keyword in keywords:
        display = make_user_facing_evidence_phrase(keyword)
        if display is None:
            continue
        key = re.sub(
            r"\b(tooling|tools|инструменты|инструментов)\b",
            "",
            display,
            flags=re.IGNORECASE,
        )
        key = re.sub(r"\s+", " ", key).strip().casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(display)
    return dedupe_subsumed_phrases(result)


def dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = re.sub(r"\s+", " ", value.strip()).lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(value.strip())
    return result


class NarrativeBuilder:
    def build_gap_mitigation_paragraph(
        self,
        *,
        vacancy_fit_narrative: dict[str, Any],
        profile_skills: list[str],
        vacancy_title: str,
    ) -> str | None:
        return build_gap_mitigation_paragraph(
            vacancy_fit_narrative=vacancy_fit_narrative,
            profile_skills=profile_skills,
            vacancy_title=vacancy_title,
        )

    def cover_letter_requirement_focus(
        self,
        *,
        matched_keywords: list[str],
        vacancy_title: str,
    ) -> str:
        return cover_letter_requirement_focus(
            matched_keywords=matched_keywords,
            vacancy_title=vacancy_title,
        )

    def cover_letter_experience_value(
        self,
        *,
        vacancy_title: str,
        matched_keywords: list[str],
        candidate_experiences: list[Any] | None,
        is_supply_management_context: Callable[..., bool],
        compress_experience_phrases: Callable[[list[str]], list[str]],
    ) -> str:
        return cover_letter_experience_value(
            vacancy_title=vacancy_title,
            matched_keywords=matched_keywords,
            candidate_experiences=candidate_experiences,
            is_supply_management_context=is_supply_management_context,
            compress_experience_phrases=compress_experience_phrases,
        )

    def cover_letter_project_value(
        self,
        *,
        selected_achievements: list[dict],
        selected_evidence: list[dict[str, Any]],
    ) -> str:
        candidates: list[tuple[str, int, str]] = []

        for item in selected_evidence:
            phrase = self.cover_letter_project_phrase(
                title=str(item.get("title") or ""),
                body=str(item.get("snippet_text") or ""),
                skills=[str(skill) for skill in item.get("skills") or []],
                fact_status=str(item.get("fact_status") or ""),
                ownership_confidence=str(
                    item.get("ownership_confidence")
                    or item.get("candidate_ownership_confidence")
                    or ""
                ),
                requires_confirmation=bool(item.get("requires_confirmation") is True),
            )
            if phrase:
                phrase = self._project_phrase_narrative_form(
                    humanize_experience_phrase(phrase)
                )
                candidates.append(
                    (
                        phrase,
                        score_alignment_item(
                            {
                                "requirement": str(item.get("title") or ""),
                                "evidence": phrase,
                                "confidence": "high"
                                if str(item.get("fact_status") or "").strip().lower()
                                in {"confirmed", "user_provided"}
                                else "medium",
                            }
                        ),
                        phrase,
                    )
                )

        for item in selected_achievements:
            phrase = self.cover_letter_project_phrase(
                title=str(item.get("title") or ""),
                body=" ".join(
                    str(item.get(field) or "")
                    for field in ("situation", "task", "action", "result", "metric_text")
                ),
                skills=[],
                fact_status=str(item.get("fact_status") or ""),
                ownership_confidence=str(
                    item.get("ownership_confidence")
                    or item.get("candidate_ownership_confidence")
                    or ""
                ),
                requires_confirmation=bool(item.get("requires_confirmation") is True),
            )
            if phrase:
                phrase = self._project_phrase_narrative_form(
                    humanize_experience_phrase(phrase)
                )
                candidates.append(
                    (
                        phrase,
                        score_alignment_item(
                            {
                                "requirement": str(item.get("title") or ""),
                                "evidence": phrase,
                                "confidence": "high"
                                if str(item.get("fact_status") or "").strip().lower()
                                in {"confirmed", "user_provided"}
                                else "medium",
                            }
                        ),
                        phrase,
                    )
                )

        if not candidates:
            return ""

        kept_bases = dedupe_subsumed_phrases(
            dedupe_preserve_order([base for base, _, _ in candidates])
        )
        kept_base_keys = {str(base).casefold() for base in kept_bases}
        project_phrases = [
            (score, phrase)
            for base, score, phrase in candidates
            if str(base).casefold() in kept_base_keys
        ]
        project_phrases = [
            phrase
            for score, phrase in sorted(project_phrases, key=lambda pair: pair[0], reverse=True)
        ]
        project_phrases = dedupe_subsumed_phrases(
            dedupe_preserve_order(project_phrases)
        )
        return self._join_project_narrative_phrases(project_phrases[:3])

    def _project_phrase_narrative_form(self, phrase: str) -> str:
        cleaned = re.sub(r"\s+", " ", str(phrase or "")).strip(" .;-–—•")
        if not cleaned:
            return ""
        return verbalize_achievement_phrase(
            cleaned,
            style=AchievementStyle.NARRATIVE,
        )

    def _join_project_narrative_phrases(self, phrases: list[str]) -> str:
        cleaned = dedupe_subsumed_phrases(
            dedupe_preserve_order(
                [
                    re.sub(r"\s+", " ", str(phrase or "")).strip(" .;-–—•")
                    for phrase in phrases
                    if str(phrase or "").strip()
                ]
            )
        )
        if not cleaned:
            return ""
        if len(cleaned) == 1:
            return cleaned[0]
        if len(cleaned) == 2:
            return f"{cleaned[0]} и {cleaned[1]}"
        return f"{', '.join(cleaned[:-1])}, а также {cleaned[-1]}"

    def cover_letter_project_phrase(
        self,
        *,
        title: str,
        body: str,
        skills: list[str],
        fact_status: str = "",
        ownership_confidence: str = "",
        requires_confirmation: bool = False,
    ) -> str:
        corpus = " ".join([title, body, " ".join(skills)]).lower()
        confirmed = str(fact_status or "").strip().lower() in {"confirmed", "user_provided"}
        low_ownership = str(ownership_confidence or "").strip().lower() in {
            "low",
            "unknown",
            "needs_review",
        }
        if requires_confirmation or low_ownership or not confirmed:
            cleaned_title = re.sub(r"\s+", " ", title).strip(" .;-–—•")
            display_title = make_user_facing_evidence_phrase(cleaned_title)
            if display_title:
                return f"проектный опыт: {display_title}"
            return "проектный опыт"

        if any(
            marker in corpus
            for marker in (
                "дизайн",
                "макет",
                "брендинг",
                "photoshop",
                "illustrator",
                "figma",
                "coreldraw",
            )
        ):
            return "разработка визуальных материалов"
        if any(marker in corpus for marker in ("computer vision", "image", "изображ", "video", "видео")):
            return "опыт обработки визуальных данных"
        if any(marker in corpus for marker in ("quality control", "контроль качества", "safety", "безопас")):
            return "опыт прикладного мониторинга и контроля"
        if any(marker in corpus for marker in ("vacancy", "резюме", "document", "review")):
            return "проектный опыт без расширения роли"
        if any(
            marker in corpus
            for marker in ("pytest", "test", "testing", "автотест", "автоматическ", "тестирован")
        ):
            return "настройки автоматического тестирования"
        if any(marker in corpus for marker in ("fastapi", "backend", "api")):
            if "fastapi" in corpus:
                return "разработка REST API на FastAPI"
            return "разработка REST API"
        if any(marker in corpus for marker in ("automation", "workflow", "openai", "telegram")):
            return "опыт автоматизации рабочих процессов с интеграциями"
        if any(marker in corpus for marker in ("analytics", "analysis", "аналит")):
            return "опыт аналитического pipeline для извлечения прикладных сигналов"

        cleaned_title = re.sub(r"\s+", " ", title).strip(" .;-–—•")
        display_title = make_user_facing_evidence_phrase(cleaned_title)
        if display_title and display_title.lower() not in {
            "technology stack from resume",
            "technologies from resume",
        }:
            return display_title
        return ""

    def project_value_should_lead(self, project_value: str) -> bool:
        lowered = str(project_value or "").lower()
        return any(
            marker in lowered
            for marker in (
                "pytest",
                "автотест",
                "автоматическ",
                "тестирован",
                "ci/cd",
                "pipeline",
                "пайплайн",
            )
        )

    def compress_experience_phrases(self, phrases: list[str]) -> list[str]:
        if not phrases:
            return []

        compression_groups = (
            {
                "patterns": [
                    r"организаци.*закуп",
                    r"управлен.*отдел.*снабжен",
                    r"(?<!водо)снабжен",
                    r"\bмтс\b",
                ],
                "compressed": "организации закупочной деятельности",
            },
            {
                "patterns": [
                    r"управлен.*склад.*запас",
                    r"склад.*остат",
                    r"склад.*запас",
                ],
                "compressed": "управления складскими запасами",
            },
            {
                "patterns": [
                    r"переговор.*поставщик",
                    r"поставщик",
                ],
                "compressed": "ведения переговоров с поставщиками",
            },
            {
                "patterns": [
                    r"договор",
                    r"претензионн.*работ",
                ],
                "compressed": "договорной работы",
            },
            {
                "patterns": [
                    r"контрол.*постав",
                    r"контрол.*отгруз",
                    r"поставк.*контрол",
                ],
                "compressed": "контроля поставок",
            },
            {
                "patterns": [
                    r"монтаж.*водоснабж",
                    r"монтаж.*канализац",
                    r"монтаж.*отоплен",
                    r"обслуживани.*инженерн",
                    r"обслуживани.*сантехническ",
                    r"обслуживани.*оборудовани",
                    r"установк.*сантехническ",
                    r"установк.*прибор",
                ],
                "compressed": "монтажа и обслуживания инженерных систем",
            },
            {
                "patterns": [
                    r"замен.*трубопровод",
                    r"ремонт.*трубопровод",
                    r"ремонт.*труб",
                    r"замен.*труб",
                    r"запорн.*арматур",
                ],
                "compressed": "ремонта трубопроводов",
            },
            {
                "patterns": [
                    r"устранени.*авари",
                    r"авари.*ситуаци",
                    r"авари.*работ",
                    r"устранени.*протеч",
                ],
                "compressed": "устранения аварийных ситуаций",
            },
            {
                "patterns": [
                    r"проверк",
                    r"осмотр",
                    r"диагностик",
                    r"профилактик",
                    r"техническ.*обслуживани",
                ],
                "compressed": "проведения профилактических осмотров",
            },
            {
                "patterns": [
                    r"техническ.*документаци",
                    r"проектн.*документаци",
                    r"сопроводител.*документаци",
                    r"отчёт.*по\s+объек",
                    r"отчет.*по\s+объек",
                    r"наряд.*заказ",
                    r"исполнител.*документаци",
                ],
                "compressed": "работы с технической документацией",
            },
        )

        compressed: list[str] = []
        used_indices: set[int] = set()

        for group in compression_groups:
            matched_indices: list[int] = []
            for index, phrase in enumerate(phrases):
                if index in used_indices:
                    continue
                lowered = phrase.lower()
                if any(re.search(pattern, lowered) for pattern in group["patterns"]):
                    matched_indices.append(index)

            if matched_indices:
                compressed.append(group["compressed"])
                used_indices.update(matched_indices)

        for index, phrase in enumerate(phrases):
            if index not in used_indices:
                compressed.append(phrase)

        return dedupe_preserve_order(compressed)

    def split_resume_focus_source(
        self,
        value: str,
        *,
        responsibility_boundaries: list[str],
    ) -> list[str]:
        text = re.sub(r"[ \t]+", " ", str(value or "")).strip(" .;-–—•")
        if not text:
            return []

        for boundary in responsibility_boundaries:
            text = re.sub(
                rf"(?<!^)\s+({re.escape(boundary)})",
                r"\n\1",
                text,
                flags=re.IGNORECASE,
            )

        parts = [
            re.sub(r"\s+", " ", part).strip(" .;-–—•")
            for part in re.split(r"\n+|\s+-\s+|[;•]+", text)
            if part.strip(" .;-–—•")
        ]
        return dedupe_preserve_order(parts)

    def specialize_resume_summary_focus_phrases(
        self,
        *,
        role: str,
        focus_phrases: list[str],
        selected_skills: list[str],
        selected_achievements: list[dict[str, Any]],
    ) -> list[str]:
        if self.is_resume_supply_management_context(
            role=role,
            focus_phrases=focus_phrases,
            selected_skills=selected_skills,
            selected_achievements=selected_achievements,
        ):
            corpus = self.resume_summary_context_corpus(
                role=role,
                focus_phrases=focus_phrases,
                selected_skills=selected_skills,
                selected_achievements=selected_achievements,
            )
            specialized: list[str] = []
            if re.search(r"(?<!водо)снабжен|закуп|мтс|материально", corpus):
                specialized.append("закупки")
            if re.search(r"поставщик|переговор", corpus):
                specialized.append("управление поставщиками")
            if re.search(r"склад|логист|остат|запас", corpus):
                specialized.append("складская логистика")
            if re.search(r"бюджет|затрат|стоимост", corpus):
                specialized.append("бюджетирование")
            if re.search(r"договор|претензи", corpus):
                specialized.append("договорная работа")
            return specialized or focus_phrases

        if self.is_resume_design_context(
            role=role,
            focus_phrases=focus_phrases,
            selected_skills=selected_skills,
            selected_achievements=selected_achievements,
        ):
            corpus = self.resume_summary_context_corpus(
                role=role,
                focus_phrases=focus_phrases,
                selected_skills=selected_skills,
                selected_achievements=selected_achievements,
            )
            specialized: list[str] = []
            if re.search(r"графическ|дизайн|визуальн|брендинг", corpus):
                specialized.append("графического дизайна")
            if re.search(r"макет|полиграф|печать", corpus):
                specialized.append("подготовки макетов к печати")
            if re.search(r"figma|photoshop|illustrator|coreldraw|типограф", corpus):
                specialized.append("работы с графическими редакторами")
            return specialized or focus_phrases

        if "сантехник" not in role.casefold():
            return focus_phrases

        corpus = self.resume_summary_context_corpus(
            role=role,
            focus_phrases=focus_phrases,
            selected_skills=selected_skills,
            selected_achievements=selected_achievements,
        )

        specialized: list[str] = []
        if re.search(r"инженерн|водоснаб|канализац|сантех", corpus):
            specialized.append("обслуживание инженерных систем")
        if re.search(r"трубопровод|запорн|ремонт|замен", corpus):
            specialized.append("ремонт трубопроводов")
        if re.search(r"авар|протеч|засор", corpus):
            specialized.append("устранение аварийных ситуаций")

        return specialized or focus_phrases

    def specialize_resume_summary_role(
        self,
        *,
        role: str,
        focus_phrases: list[str],
        selected_skills: list[str],
        selected_achievements: list[dict[str, Any]],
    ) -> str:
        if self.is_resume_supply_management_context(
            role=role,
            focus_phrases=focus_phrases,
            selected_skills=selected_skills,
            selected_achievements=selected_achievements,
        ):
            return "Руководитель в сфере материально-технического обеспечения"
        return role

    def is_resume_supply_management_context(
        self,
        *,
        role: str,
        focus_phrases: list[str],
        selected_skills: list[str],
        selected_achievements: list[dict[str, Any]],
    ) -> bool:
        corpus = self.resume_summary_context_corpus(
            role=role,
            focus_phrases=focus_phrases,
            selected_skills=selected_skills,
            selected_achievements=selected_achievements,
        )
        has_supply_domain = bool(
            re.search(r"(?<!водо)снабжен|закуп|мтс|материально|поставщик|склад|логист", corpus)
        )
        has_management_signal = bool(
            re.search(r"начальник|руковод|управлен|бюджет|переговор|договор|контрол", corpus)
        )
        return has_supply_domain and has_management_signal

    def is_resume_design_context(
        self,
        *,
        role: str,
        focus_phrases: list[str],
        selected_skills: list[str],
        selected_achievements: list[dict[str, Any]],
    ) -> bool:
        corpus = self.resume_summary_context_corpus(
            role=role,
            focus_phrases=focus_phrases,
            selected_skills=selected_skills,
            selected_achievements=selected_achievements,
        )
        return bool(
            re.search(
                r"дизайн|графическ|photoshop|illustrator|figma|coreldraw|брендинг|типограф|макет",
                corpus,
            )
        )

    def resume_summary_context_corpus(
        self,
        *,
        role: str,
        focus_phrases: list[str],
        selected_skills: list[str],
        selected_achievements: list[dict[str, Any]],
    ) -> str:
        return " ".join(
            [
                str(role or ""),
                *[str(value or "") for value in focus_phrases],
                *[str(value or "") for value in selected_skills],
                *[str(item.get("title") or "") for item in selected_achievements],
            ]
        ).casefold()

    def add_project_narratives(
        self,
        selected_achievements: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        enriched: list[dict[str, Any]] = []

        for item in selected_achievements:
            enriched_item = dict(item)
            title = str(item.get("title") or "").lower()
            action = str(item.get("action") or "")
            skills = [
                str(skill).strip()
                for skill in (item.get("skills") or [])
                if str(skill).strip()
            ]

            corpus = " ".join([title, action, " ".join(skills)]).lower()

            if "workflow orchestration" in corpus or "ai workflow" in corpus:
                enriched_item["narrative"] = (
                    "workflow/orchestration implementation signals; ownership requires review"
                )
            elif "fastapi" in corpus or "backend" in corpus:
                enriched_item["narrative"] = (
                    "backend/API implementation signals; ownership requires review"
                )
            elif "computer vision" in corpus or "мониторинг" in corpus:
                enriched_item["narrative"] = (
                    "AI/CV pipeline для анализа изображений или видео и поддержки "
                    "прикладного мониторинга"
                )
            elif "analytics" in corpus or "анализ" in corpus:
                enriched_item["narrative"] = (
                    "аналитический pipeline для обработки данных и извлечения полезных сигналов"
                )

            enriched.append(enriched_item)

        return enriched

    def build_project_sections(
        self,
        selected_achievements: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}

        for item in selected_achievements:
            if not self.allows_strong_project_claim(item):
                continue
            project_name = self.project_name_from_achievement(item)
            role = self.project_role_from_achievement(item)
            bullets = self.project_bullets_from_achievement(item)
            if not bullets:
                continue

            section = grouped.setdefault(
                project_name,
                {
                    "project": project_name,
                    "role": role,
                    "bullets": [],
                },
            )
            if not section.get("role") and role:
                section["role"] = role
            section["bullets"] = self.dedupe_project_bullets(
                [*section["bullets"], *bullets]
            )[:5]

        return list(grouped.values())[:4]

    def allows_strong_project_claim(self, achievement: dict[str, Any]) -> bool:
        fact_status = str(achievement.get("fact_status") or "").strip().lower()
        ownership_confidence = str(
            achievement.get("ownership_confidence")
            or achievement.get("candidate_ownership_confidence")
            or "medium"
        ).strip().lower()
        requires_confirmation = bool(achievement.get("requires_confirmation") is True)

        if requires_confirmation:
            return False
        if ownership_confidence in {"low", "unknown", "needs_review"}:
            return False
        return fact_status in {"confirmed", "user_provided"}

    def dedupe_project_bullets(self, bullets: list[str]) -> list[str]:
        selected: list[str] = []
        seen_text: set[str] = set()
        seen_concepts: set[str] = set()

        for bullet in bullets:
            cleaned = re.sub(r"\s+", " ", str(bullet).strip())
            normalized = cleaned.lower()
            if not normalized or normalized in seen_text:
                continue

            concept = self.project_bullet_concept(normalized)
            if concept and concept in seen_concepts:
                continue

            seen_text.add(normalized)
            if concept:
                seen_concepts.add(concept)
            selected.append(cleaned)

        return selected

    def project_bullet_concept(self, normalized_bullet: str) -> str | None:
        if "fastapi" in normalized_bullet or "backend" in normalized_bullet:
            return "backend"
        if "workflow" in normalized_bullet and (
            "orchestration" in normalized_bullet
            or "генерации" in normalized_bullet
        ):
            return "workflow"
        if "persistence" in normalized_bullet or "postgresql" in normalized_bullet:
            return "persistence"
        if "computer vision" in normalized_bullet or "мониторинг" in normalized_bullet:
            return "computer_vision"
        if "analytics" in normalized_bullet or "аналит" in normalized_bullet:
            return "analytics"
        return None

    def project_name_from_achievement(self, achievement: dict[str, Any]) -> str:
        title = str(achievement.get("title") or "").strip()
        if title:
            return title

        corpus = self.achievement_semantic_corpus(achievement)

        if any(marker in corpus for marker in ("computer vision", "cv", "изображен", "video", "видео")):
            return "Visual Data Processing Project"
        if any(marker in corpus for marker in ("analytics", "data pipeline", "аналит")):
            return "Analytics Project"
        if any(marker in corpus for marker in ("workflow orchestration", "ai workflow", "pipeline")):
            return "Workflow Implementation Project"
        if any(marker in corpus for marker in ("backend", "fastapi", "api")):
            return "Backend Implementation Project"
        return "Project Evidence"

    def project_role_from_achievement(self, achievement: dict[str, Any]) -> str:
        corpus = self.achievement_semantic_corpus(achievement)

        if any(marker in corpus for marker in ("computer vision", "cv", "изображен", "video", "видео")):
            return "Visual Data Processing Evidence"
        if any(marker in corpus for marker in ("workflow orchestration", "ai workflow", "pipeline")):
            return "Workflow Implementation Evidence"
        if any(marker in corpus for marker in ("fastapi", "backend", "api")):
            return "Backend/API Implementation Evidence"
        if any(marker in corpus for marker in ("analytics", "data pipeline", "аналит")):
            return "Analytics Evidence"
        return "Project Evidence"

    def project_bullets_from_achievement(
        self,
        achievement: dict[str, Any],
    ) -> list[str]:
        corpus = self.achievement_semantic_corpus(achievement)
        bullets: list[str] = []

        if "computer vision" in corpus or "мониторинг" in corpus or "quality control" in corpus:
            bullets.append(self.computer_vision_impact_bullet(corpus))
        if "analytics" in corpus or "аналит" in corpus:
            bullets.append(
                "Построил аналитический pipeline для выявления прикладных сигналов "
                "и поддержки решений"
            )
        if "workflow orchestration" in corpus or "ai workflow" in corpus:
            bullets.append("Зафиксированы workflow/orchestration implementation signals")
        if "fastapi" in corpus or "backend" in corpus:
            bullets.append("Зафиксированы backend/API implementation signals")
        if any(marker in corpus for marker in ("evidence review", "review flow", "evidence-review")):
            bullets.append("Зафиксированы evidence-review implementation signals")
        if any(marker in corpus for marker in ("postgresql", "sqlalchemy", "persistence layer")):
            bullets.append("Зафиксированы persistence-layer implementation signals")
        if any(marker in corpus for marker in ("docker", "redis", "infrastructure")):
            bullets.append("Зафиксированы infrastructure implementation signals")

        narrative = str(achievement.get("narrative") or "").strip()
        if narrative and not bullets:
            bullets.append(self.sentence_to_project_bullet(narrative))

        action = str(achievement.get("action") or "").strip()
        if action and not bullets:
            bullets.append(self.sentence_to_project_bullet(action))

        result = str(achievement.get("metric_text") or achievement.get("result") or "").strip()
        if result:
            bullets.append(f"Зафиксировал результат: {result}")

        return dedupe_preserve_order(bullets)[:5]

    def computer_vision_impact_bullet(self, corpus: str) -> str:
        if any(
            marker in corpus
            for marker in (
                "computer vision",
                "cv",
                "изображен",
                "video",
                "видео",
            )
        ):
            return (
                "Реализовал обработку изображений и видео "
                "для прикладных задач мониторинга и контроля"
            )

        if any(marker in corpus for marker in ("безопас", "safety", "security")):
            return (
                "Реализовал pipeline прикладного мониторинга "
                "с использованием AI/CV компонентов"
            )

        return (
            "Реализовал AI/CV pipeline "
            "для обработки визуальных данных"
        )

    def achievement_semantic_corpus(self, achievement: dict[str, Any]) -> str:
        return " ".join(
            [
                str(achievement.get("title") or ""),
                str(achievement.get("task") or ""),
                str(achievement.get("action") or ""),
                str(achievement.get("result") or ""),
                str(achievement.get("metric_text") or ""),
                str(achievement.get("narrative") or ""),
                str(achievement.get("reason") or ""),
                " ".join(str(skill) for skill in (achievement.get("skills") or [])),
            ]
        ).lower()

    def sentence_to_project_bullet(self, text: str) -> str:
        cleaned = re.sub(r"\s+", " ", text).strip(" .;-–—•")
        if not cleaned:
            return "Описал проектный вклад на основе подтверждённых фактов"

        first_word = cleaned.split(" ", 1)[0].lower()
        if first_word in {"разработал", "реализовал", "спроектировал", "интегрировал", "построил"}:
            return cleaned
        return f"Реализовал {cleaned}"

    def render_gap_topics(self, critical_gaps: list[str]) -> str | None:
        return render_gap_topics(critical_gaps)

    def gap_topic_label(self, gap: str) -> str:
        return gap_topic_label(gap)

    def gap_mitigation_allowed(self, item: dict[str, Any]) -> bool:
        return gap_mitigation_allowed(item)

    def score_gap_for_cover_letter(self, label: str) -> int:
        return score_gap_for_cover_letter(label)

    def to_gap_case(self, gap: str) -> str:
        return to_gap_case(gap)

    def dedupe_gap_keywords(self, keywords: list[str]) -> list[str]:
        return dedupe_gap_keywords(keywords)
