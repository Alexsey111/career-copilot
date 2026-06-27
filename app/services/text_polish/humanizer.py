# app\services\text_polish\humanizer.py

from __future__ import annotations

import re

from app.domain.evidence_alignment import humanize_experience_phrase
from app.domain.text_normalization import clean_vacancy_title, dedupe_subsumed_phrases


def dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for value in values:
        normalized = re.sub(r"\s+", " ", str(value or "").strip()).lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(str(value).strip())

    return result


def deterministic_variant_key(*values: str) -> int:
    corpus = "|".join(str(value or "") for value in values)
    return sum(ord(ch) for ch in corpus) % 1000


def pick_deterministic_phrase(
    variants: list[str],
    *,
    key_values: list[str],
) -> str:
    if not variants:
        return ""
    key = deterministic_variant_key(*key_values)
    return variants[key % len(variants)]


def lowercase_sentence_start(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(value or "")).strip(" .;-–—•")
    if not cleaned:
        return ""
    return cleaned[:1].lower() + cleaned[1:]


def join_cover_letter_phrases(phrases: list[str]) -> str:
    if not phrases:
        return "релевантными для роли задачами"
    if len(phrases) == 1:
        return phrases[0]
    if len(phrases) == 2:
        return f"{phrases[0]} и {phrases[1]}"
    return f"{', '.join(phrases[:-1])} и {phrases[-1]}"


def join_experience_phrases(phrases: list[str]) -> str:
    if not phrases:
        return ""
    if len(phrases) == 1:
        return phrases[0]
    if len(phrases) == 2:
        return f"{phrases[0]} и {phrases[1]}"
    return f"{phrases[0]}, {phrases[1]} и {phrases[2]}"


def cover_letter_scope_list(value: str) -> str:
    replacements = (
        ("организации ", "организацию "),
        ("управления ", "управление "),
        ("ведения ", "ведение "),
        ("контроля ", "контроль "),
        ("бюджетирования", "бюджетирование"),
        ("договорной и претензионной работы", "договорную и претензионную работу"),
        ("договорной работы", "договорную работу"),
        ("претензионной работы", "претензионную работу"),
    )
    result = re.sub(r"\s+", " ", str(value or "")).strip(" .;-–—•")
    for source, target in replacements:
        result = re.sub(rf"(?<!\w){re.escape(source)}", target, result, flags=re.IGNORECASE)
    return result


def to_activity_case(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(value or "")).strip(" .;-–—•")
    return humanize_experience_phrase(
        cleaned,
        grammatical_case="instrumental",
    )


def cover_letter_activity_list(value: str) -> str:
    raw_parts = [
        re.sub(r"\s+", " ", part).strip(" .;-–—•")
        for part in re.split(r"\s*;\s*", str(value or ""))
        if str(part or "").strip(" .;-–—•")
    ]

    fixed_parts: list[str] = []
    for part in raw_parts:
        lowered = part.casefold()
        if lowered in {"судебное сопровождение", "судебного сопровождения"}:
            fixed_parts.append("судебным сопровождением")
        elif lowered in {"консультирование клиентов", "консультирования клиентов"}:
            fixed_parts.append("консультированием клиентов")
        else:
            fixed_parts.append(to_activity_case(part))

    phrases = dedupe_preserve_order([phrase for phrase in fixed_parts if phrase])
    return join_cover_letter_phrases(phrases)


def cover_letter_activity_verb(
    *,
    candidate_experiences: list[object] | None,
    selected_achievements: list[dict],
) -> str:
    text_parts = [
        str(item.get("title") or "")
        for item in selected_achievements
        if isinstance(item, dict)
    ]
    for exp in candidate_experiences or []:
        text_parts.append(str(getattr(exp, "description_raw", "") or ""))
    text = " ".join(text_parts).lower()
    if any(
        marker in text
        for marker in (
            "занималась",
            "подготовила",
            "сократила",
            "настроила",
            "внедрила",
            "вела",
            "участвовала",
        )
    ):
        return "занималась"
    if any(
        marker in text
        for marker in (
            "занимался",
            "подготовил",
            "сократил",
            "настроил",
            "внедрил",
            "вёл",
            "вел",
            "участвовал",
        )
    ):
        return "занимался"
    return "занимался"


def infer_candidate_gender_from_text(
    *,
    full_name: str | None = None,
    text: str = "",
) -> str:
    corpus = " ".join([str(full_name or ""), str(text or "")]).casefold()

    female_markers = (
        "подготовила",
        "снизила",
        "разработала",
        "занималась",
        "вела",
        "участвовала",
        "готова",
    )
    male_markers = (
        "подготовил",
        "снизил",
        "разработал",
        "занимался",
        "вел",
        "вёл",
        "участвовал",
        "готов",
    )

    if any(marker in corpus for marker in female_markers):
        return "female"
    if any(marker in corpus for marker in male_markers):
        return "male"

    first_name = str(full_name or "").strip().split(" ")[0].casefold()
    if first_name.endswith(("а", "я")):
        return "female"

    return "male"


def cover_letter_role_instrumental(vacancy_title: str) -> str:
    role = clean_vacancy_title(vacancy_title)
    lowered = role.lower()
    role_map = {
        "бухгалтер": "бухгалтером",
        "логист": "логистом",
        "кладовщик": "кладовщиком",
        "юрист": "юристом",
        "терапевт": "терапевтом",
    }
    if lowered in role_map:
        return role_map[lowered]
    if "заместитель начальника" in lowered and "снабжен" in lowered:
        return "заместителем начальника отдела снабжения"
    if "супервайзер" in lowered:
        return role.lower()
    return role.lower()


def build_cover_letter_experience_sentence(
    *,
    vacancy_title: str,
    experience_value: str,
    candidate_experiences: list[object] | None,
    selected_achievements: list[dict],
    is_supply_management_context: bool,
) -> str:
    if is_supply_management_context:
        return f"Мой опыт включает {cover_letter_scope_list(experience_value)}."

    role = cover_letter_role_instrumental(vacancy_title)
    verb = cover_letter_activity_verb(
        candidate_experiences=candidate_experiences,
        selected_achievements=selected_achievements,
    )
    activities = cover_letter_activity_list(experience_value)
    return f"За время работы {role} я {verb} {activities}."


def format_summary_focus_phrases(phrases: list[str]) -> str:
    cleaned = [
        humanize_experience_phrase(
            re.sub(r"\s+", " ", str(value or "")).strip(" .;-–—•")
        )
        for value in phrases
        if str(value or "").strip()
    ]
    cleaned = dedupe_subsumed_phrases(
        dedupe_preserve_order([item for item in cleaned if item])
    )
    if not cleaned:
        return "релевантных профессиональных задач"
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return " и ".join(cleaned)
    return f"{', '.join(cleaned[:-1])} и {cleaned[-1]}"


def humanize_resume_role(vacancy_title: str) -> str:
    role = clean_vacancy_title(vacancy_title) or "кандидат"
    normalized = role.casefold()
    if normalized == "терапевт":
        return "Врач-терапевт"
    if normalized.startswith("вакансия "):
        role = role[len("вакансия "):].strip() or role
    return role[:1].upper() + role[1:]


def role_to_instrumental(role: str) -> str:
    normalized = re.sub(r"\s+", " ", str(role or "")).strip().casefold()
    known_roles = {
        "сантехник": "сантехником",
        "слесарь-сантехник": "слесарем-сантехником",
        "бухгалтер": "бухгалтером",
        "юрист": "юристом",
        "терапевт": "врачом-терапевтом",
        "врач-терапевт": "врачом-терапевтом",
    }
    return known_roles.get(normalized, "")


def fix_resume_achievement_opening_role_case(value: str, role: str) -> str:
    instrumental_role = role_to_instrumental(role)
    if not instrumental_role:
        return value

    normalized_role = re.sub(r"\s+", " ", str(role or "")).strip()
    if not normalized_role:
        return value

    return re.sub(
        rf"^{re.escape(normalized_role)}(\s+я\b)",
        rf"{instrumental_role}\1",
        value,
        flags=re.IGNORECASE,
    )


class CoverLetterHumanizer:
    def polish_section(self, value: str) -> str:
        cleaned = re.sub(r"[ \t]+", " ", str(value or "")).strip()
        cleaned = re.sub(r"\s+([,.!?;:])", r"\1", cleaned)
        return cleaned

    def polish_sections(
        self,
        *,
        opening: str,
        relevance_paragraph: str,
        closing: str,
    ) -> dict[str, str]:
        return {
            "opening": self.polish_section(opening),
            "relevance_paragraph": self.polish_section(relevance_paragraph),
            "closing": self.polish_section(closing),
        }

    def scope_list(self, value: str) -> str:
        return cover_letter_scope_list(value)

    def activity_list(self, value: str) -> str:
        return cover_letter_activity_list(value)

    def activity_verb(
        self,
        *,
        candidate_experiences: list[object] | None,
        selected_achievements: list[dict],
    ) -> str:
        return cover_letter_activity_verb(
            candidate_experiences=candidate_experiences,
            selected_achievements=selected_achievements,
        )

    def experience_opening_phrase(
        self,
        *,
        vacancy_title: str,
        experience_value: str,
    ) -> str:
        return pick_deterministic_phrase(
            [
                "За время работы",
                "В своей практике",
                "В профессиональной деятельности",
            ],
            key_values=[vacancy_title, experience_value],
        )

    def candidate_gender(
        self,
        *,
        full_name: str | None = None,
        text: str = "",
    ) -> str:
        return infer_candidate_gender_from_text(
            full_name=full_name,
            text=text,
        )

    def ready_word(self, *, gender: str) -> str:
        return "готова" if gender == "female" else "готов"

    def glad_word(self, *, gender: str) -> str:
        return "рада" if gender == "female" else "рад"

    def role_instrumental(self, vacancy_title: str) -> str:
        return cover_letter_role_instrumental(vacancy_title)

    def experience_sentence(
        self,
        *,
        vacancy_title: str,
        experience_value: str,
        candidate_experiences: list[object] | None,
        selected_achievements: list[dict],
        is_supply_management_context: bool,
    ) -> str:
        return build_cover_letter_experience_sentence(
            vacancy_title=vacancy_title,
            experience_value=experience_value,
            candidate_experiences=candidate_experiences,
            selected_achievements=selected_achievements,
            is_supply_management_context=is_supply_management_context,
        )

    def project_result_sentence(self, project_value: str) -> str:
        return f"Среди реализованных проектов и инициатив — {project_value}."

    def closing_contact_sentence(
        self,
        *,
        gender: str,
        vacancy_title: str,
        focus: str = "",
    ) -> str:
        glad = self.glad_word(gender=gender)
        return pick_deterministic_phrase(
            [
                f"Буду {glad} обсудить, чем мой опыт может быть полезен вашей команде.",
                "С удовольствием подробнее расскажу о своём опыте на интервью.",
                "Буду признательна за возможность обсудить, как мой опыт может быть полезен вашей команде."
                if gender == "female"
                else "Буду признателен за возможность обсудить, как мой опыт может быть полезен вашей команде.",
            ],
            key_values=[gender, vacancy_title, focus],
        )

    def achievement_result_sentence(self, achievements: list[str]) -> str:
        return (
            "Практический результат моей работы — "
            + "; ".join(achievements[:2])
            + "."
        )

    def join_phrases(self, phrases: list[str]) -> str:
        return join_cover_letter_phrases(phrases)

    def join_experience_phrases(self, phrases: list[str]) -> str:
        return join_experience_phrases(phrases)

    def to_activity_case(self, value: str) -> str:
        return to_activity_case(value)

    def lowercase_sentence_start(self, value: str) -> str:
        return lowercase_sentence_start(value)
