#  app\services\resume_renderer.py

from __future__ import annotations


def render_resume(content_json: dict) -> str:
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
    lines.append("ЦЕЛЕВАЯ ПОЗИЦИЯ")
    lines.append(vacancy["title"])

    lines.append("")
    lines.append("КРАТКОЕ РЕЗЮМЕ")
    vacancy_aligned_summary = sections.get("vacancy_aligned_summary")
    if vacancy_aligned_summary:
        lines.append(vacancy_aligned_summary)
    for bullet in sections["summary_bullets"]:
        lines.append(f"- {bullet}")

    relevant_to_vacancy = sections.get("relevant_to_vacancy") or []
    if relevant_to_vacancy:
        lines.append("")
        lines.append("РЕЛЕВАНТНО ДЛЯ ВАКАНСИИ")
        for item in relevant_to_vacancy:
            lines.append(f"- {item}")

    competency_mapping = sections.get("competency_mapping") or []
    if competency_mapping:
        lines.append("")
        lines.append("КАРТА КОМПЕТЕНЦИЙ")
        for item in competency_mapping:
            competency = item.get("competency") or item.get("label") or item.get("keyword")
            evidence = item.get("evidence") or item.get("source") or item.get("evidence_title")
            if competency and evidence:
                lines.append(f"- {competency}: {evidence}")
            elif competency:
                lines.append(f"- {competency}")

    lines.append("")
    lines.append("КЛЮЧЕВЫЕ НАВЫКИ")
    for skill in sections["skills"]:
        lines.append(f"- {skill}")

    experience_items = sections["experience"]
    if experience_items:
        lines.append("")
        lines.append("ОПЫТ РАБОТЫ")
        for item in experience_items:
            lines.append(f"{item['role']} — {item['company']} ({item['period']})")
            if item.get("description_raw"):
                lines.append(f"- {item['description_raw']}")

    education_items = sections.get("education") or []
    if education_items:
        lines.append("")
        lines.append("ОБРАЗОВАНИЕ")
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
        lines.append("КУРСЫ")
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
        lines.append("СТАЖИРОВКИ / УЧЕБНЫЕ ПРОЕКТЫ")
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
    if project_sections or selected_achievements:
        lines.append("")
        lines.append("РЕЛЕВАНТНЫЕ ПРОЕКТЫ")

    if project_sections:
        for project in project_sections:
            project_name = project.get("project") or "Проект"
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
            title = item.get("title") or "Проект"
            narrative = item.get("narrative") or item.get("action") or item.get("task")
            metric_text = item.get("metric_text") or item.get("result")

            if narrative and metric_text:
                lines.append(f"- {title} — {narrative} Результат: {metric_text}")
            elif narrative:
                lines.append(f"- {title} — {narrative}")
            elif metric_text:
                lines.append(f"- {title} — {metric_text}")
            else:
                lines.append(f"- {title}")

    return "\n".join(lines).strip()


def render_cover_letter(content_json: dict) -> str:
    sections = content_json["sections"]

    return (
        f"{sections['opening']}\n\n"
        f"{sections['relevance_paragraph']}\n\n"
        f"{sections['closing']}"
    ).strip()
