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

    lines.append("")
    lines.append("ЦЕЛЕВАЯ ПОЗИЦИЯ")
    lines.append(vacancy["title"])

    lines.append("")
    lines.append("КРАТКОЕ РЕЗЮМЕ")
    for bullet in sections["summary_bullets"]:
        lines.append(f"- {bullet}")

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

    selected_achievements = sections["selected_achievements"]
    if selected_achievements:
        lines.append("")
        lines.append("РЕЛЕВАНТНЫЕ ПРОЕКТЫ")
        for item in selected_achievements:
            metric_text = item.get("metric_text")
            if metric_text:
                lines.append(f"- {item['title']} — {metric_text}")
            else:
                lines.append(f"- {item['title']}")

    return "\n".join(lines).strip()


def render_cover_letter(content_json: dict) -> str:
    sections = content_json["sections"]

    return (
        f"{sections['opening']}\n\n"
        f"{sections['relevance_paragraph']}\n\n"
        f"{sections['closing']}"
    ).strip()
