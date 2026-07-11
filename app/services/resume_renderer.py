#  app\services\resume_renderer.py

from __future__ import annotations

import re

from app.domain.markets import normalize_market
from app.domain.text_normalization import clean_vacancy_title

# Локализация заголовков секций резюме по рынку (Этап 7). Порядок секций
# неизменен — меняются только строки-заголовки и инлайн-литералы.
RESUME_SECTION_HEADINGS = {
    "ru": {
        "target_position": "ЦЕЛЕВАЯ ПОЗИЦИЯ",
        "summary": "КРАТКОЕ РЕЗЮМЕ",
        "skills": "КЛЮЧЕВЫЕ НАВЫКИ",
        "experience": "ОПЫТ РАБОТЫ",
        "education": "ОБРАЗОВАНИЕ",
        "courses": "КУРСЫ",
        "internships": "СТАЖИРОВКИ / УЧЕБНЫЕ ПРОЕКТЫ",
        "projects": "РЕЛЕВАНТНЫЕ ПРОЕКТЫ",
        "achievements": "КЛЮЧЕВЫЕ ДОСТИЖЕНИЯ",
    },
    "eu": {
        "target_position": "TARGET ROLE",
        "summary": "SUMMARY",
        "skills": "KEY SKILLS",
        "experience": "EXPERIENCE",
        "education": "EDUCATION",
        "courses": "COURSES",
        "internships": "INTERNSHIPS / ACADEMIC PROJECTS",
        "projects": "RELEVANT PROJECTS",
        "achievements": "KEY ACHIEVEMENTS",
    },
    "us": {
        "target_position": "TARGET ROLE",
        "summary": "SUMMARY",
        "skills": "KEY SKILLS",
        "experience": "EXPERIENCE",
        "education": "EDUCATION",
        "courses": "COURSES",
        "internships": "INTERNSHIPS / ACADEMIC PROJECTS",
        "projects": "RELEVANT PROJECTS",
        "achievements": "KEY ACHIEVEMENTS",
    },
}

# ATS-безопасный суффикс для неподтверждённых достижений (круглые скобки не
# ломают линейную структуру; литерал fact_status не утекает в текст).
UNVERIFIED_SUFFIX = {
    "ru": " (неподтверждено)",
    "eu": " (unverified)",
    "us": " (unverified)",
}

RESULT_LABEL = {
    "ru": "Результат:",
    "eu": "Result:",
    "us": "Result:",
}

PROJECT_FALLBACK = {
    "ru": "Проект",
    "eu": "Project",
    "us": "Project",
}


def _resolve_market(content_json: dict, market: str | None) -> str:
    """Рынок читается из явного аргумента, затем из content_json (meta.market или
    корневого market), иначе дефолт RU. Так документ в БД самодокументирован —
    повторный рендер (экспорт TXT/MD) восстанавливает язык из content_json."""
    if market:
        return normalize_market(market)
    meta = content_json.get("meta") or {}
    return normalize_market(meta.get("market") or content_json.get("market"))


def render_resume(content_json: dict, market: str | None = None) -> str:
    candidate = content_json["candidate"]
    vacancy = content_json["target_vacancy"]
    sections = content_json["sections"]

    # INARIANT (Этап 7): candidate header содержит только full_name/headline/
    # location/контакты. photo/date_of_birth/gender НИКОГДА не рендерятся
    # независимо от market — этих полей нет в модели by design (EU/US
    # anti-discrimination: EEOC, EU Directive 2000/78/EC, GDPR Art.9).
    market_key = _resolve_market(content_json, market)
    headings = RESUME_SECTION_HEADINGS[market_key]
    suffix_text = UNVERIFIED_SUFFIX[market_key]
    result_label = RESULT_LABEL[market_key]
    project_fallback = PROJECT_FALLBACK[market_key]

    lines: list[str] = []

    if candidate.get("full_name"):
        lines.append(candidate["full_name"])
    if candidate.get("headline"):
        lines.append(candidate["headline"])
    if candidate.get("location"):
        lines.append(candidate["location"])
    contacts = candidate.get("contacts") or {}
    contact_parts = [
        contacts.get("email"),
        contacts.get("phone"),
        contacts.get("github"),
        contacts.get("telegram"),
    ]
    contact_line = " | ".join(str(item) for item in contact_parts if item)
    if contact_line:
        lines.append(contact_line)

    lines.append("")
    lines.append(headings["target_position"])
    title = clean_vacancy_title(vacancy.get("title"))
    lines.append(title)

    lines.append("")
    lines.append(headings["summary"])
    vacancy_aligned_summary = sections.get("vacancy_aligned_summary")
    if vacancy_aligned_summary:
        lines.append(vacancy_aligned_summary)
    # summary_bullets are kept in content_json for trace/review,
    # but not rendered into final ATS-safe resume text.
    # Vacancy fit narrative, relevance lists, and competency mapping are review
    # metadata. They stay in content_json, but must not leak into the final resume.

    lines.append("")
    lines.append(headings["skills"])
    for skill in sections["skills"]:
        lines.append(f"- {skill}")

    experience_items = sections["experience"]
    if experience_items:
        lines.append("")
        lines.append(headings["experience"])
        for item in experience_items:
            lines.append(f"{item['role']} — {item['company']} ({item['period']})")
            if item.get("description_raw"):
                description_lines = [
                    line.strip(" -–—•")
                    for line in str(item["description_raw"]).splitlines()
                    if line.strip()
                ]

                for line in description_lines:
                    lines.append(f"- {line}")

    education_items = sections.get("education") or []
    if education_items:
        lines.append("")
        lines.append(headings["education"])
        for item in education_items:
            if isinstance(item, dict):
                details = item.get("details")
                institution = item.get("institution")
                degree = item.get("degree")
                specialty = item.get("specialty")
                period = item.get("period")

                parts = [
                    part
                    for part in [institution, degree, specialty, period]
                    if part
                ]
                if details:
                    lines.append(str(details))
                elif parts:
                    lines.append(" — ".join(str(part) for part in parts))
            else:
                lines.append(str(item))

    course_items = sections.get("courses") or []
    if course_items:
        lines.append("")
        lines.append(headings["courses"])
        for item in course_items:
            if isinstance(item, dict):
                details = item.get("details")
                provider = item.get("provider")
                title = item.get("title")
                year = item.get("year")
                parts = [part for part in [provider, year, title] if part]
                if details:
                    lines.append(str(details))
                elif parts:
                    lines.append(" — ".join(str(part) for part in parts))
            else:
                lines.append(str(item))

    internship_items = sections.get("internships") or []
    if internship_items:
        lines.append("")
        lines.append(headings["internships"])
        for item in internship_items:
            if isinstance(item, dict):
                details = item.get("details")
                title = item.get("title")
                organization = item.get("organization") or item.get("provider")
                period = item.get("period") or item.get("year")
                snippet_text = item.get("snippet_text")
                parts = [part for part in [title, organization, period] if part]

                if details:
                    lines.append(str(details))
                elif parts:
                    lines.append(" — ".join(str(part) for part in parts))
                elif snippet_text:
                    lines.append(str(snippet_text))
            else:
                lines.append(str(item))

    project_sections = sections.get("project_sections") or []
    selected_achievements = sections["selected_achievements"]
    if project_sections:
        lines.append("")
        lines.append(headings["projects"])
    elif selected_achievements:
        lines.append("")
        lines.append(headings["achievements"])

    if project_sections:
        for project in project_sections:
            project_name = project.get("project") or project_fallback
            role = project.get("role")
            bullets = project.get("bullets") or []

            lines.append("")
            lines.append(str(project_name))
            if role:
                lines.append(str(role))
            for bullet in bullets:
                lines.append(f"- {bullet}")
    elif selected_achievements:
        for item in selected_achievements:
            title = item.get("title") or project_fallback
            narrative = item.get("narrative") or item.get("action") or item.get("task")
            metric_text = item.get("metric_text") or item.get("result")
            fact_status = str(item.get("fact_status") or "").strip().lower()
            suffix = "" if fact_status in {"confirmed", "user_provided", ""} else suffix_text

            if narrative and metric_text:
                lines.append(f"- {title} — {narrative} {result_label} {metric_text}{suffix}")
            elif narrative:
                lines.append(f"- {title} — {narrative}{suffix}")
            elif metric_text:
                lines.append(f"- {title} — {metric_text}{suffix}")
            else:
                lines.append(f"- {title}{suffix}")

    return "\n".join(lines).strip()


def render_cover_letter(content_json: dict) -> str:
    sections = content_json["sections"]

    return (
        f"{sections['opening']}\n\n"
        f"{sections['relevance_paragraph']}\n\n"
        f"{sections['closing']}"
    ).strip()
