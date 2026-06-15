# frontend\streamlit\components\document_review_workspace.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import streamlit as st

from api_client import CareerCopilotApiClient


@dataclass(frozen=True, slots=True)
class ReviewDocumentDescriptor:
    document_id: str
    title: str
    document_kind: str
    vacancy_id: str | None = None
    review_status: str | None = None
    created_at: str | None = None


def _humanize_document_kind(document_kind: str) -> str:
    mapping = {
        "resume": "Резюме",
        "cover_letter": "Сопроводительное письмо",
    }
    return mapping.get(document_kind, document_kind.replace("_", " ").title())


def _humanize_review_status(review_status: str | None) -> str:
    if not review_status:
        return "—"
    return {
        "draft": "черновик",
        "approved": "утверждён",
    }.get(review_status, review_status)


def _fact_status_badge(fact_status: str | None) -> str:
    status = str(fact_status or "").strip().lower()
    labels = {
        "confirmed": "✓ Подтверждено пользователем",
        "user_provided": "✓ Есть в резюме/профиле",
        "needs_confirmation": "⚠ Требует подтверждения",
        "partial": "⚠ Подтверждено частично",
        "rejected": "✗ Отклонено",
        "unverified": "⚠ Требует проверки",
    }
    return labels.get(status, "⚠ Требует проверки")


def _humanize_evidence_strength(value: Any) -> str:
    strength = str(value or "").strip().lower()
    return {
        "strong": "сильное подтверждение",
        "medium": "частичное подтверждение",
        "weak": "слабое подтверждение",
    }.get(strength, "требует проверки")


def _humanize_selection_reason(reason: Any) -> str:
    text = str(reason or "").strip()
    if not text or text == "—":
        return "Связано с требованиями вакансии и выбранным проектным опытом."

    lowered = text.lower()
    replacements = {
        "ai_relevance": "Связано с AI/automation опытом",
        "evidence_bank_project": "Выбрано из подтверждённых проектных доказательств",
        "keyword_overlap": "Совпадает с требованиями вакансии",
        "skills overlap": "Навыки совпадают с требованиями вакансии",
        "snippet text overlap": "Описание проекта совпадает с требованиями вакансии",
        "related skill overlap": "Связанный навык поддерживает требование вакансии",
    }
    for key, label in replacements.items():
        if key in lowered:
            return label
    return text


def _text_blob(*values: Any) -> str:
    parts: list[str] = []
    for value in values:
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
        elif isinstance(value, dict):
            parts.extend(str(item) for item in value.values())
        else:
            parts.append(str(value or ""))
    return " ".join(parts).casefold()


def _project_fit_bullets(
    *,
    detail: dict[str, Any],
    matched_keywords: list[Any],
) -> list[str]:
    blob = _text_blob(
        detail.get("title"),
        detail.get("reason"),
        detail.get("snippet_text"),
        detail.get("skills"),
        detail.get("star_summary"),
    )
    bullets: list[str] = []

    keyword_labels = [
        str(keyword).strip()
        for keyword in matched_keywords
        if str(keyword).strip()
    ]
    for keyword in keyword_labels:
        if keyword.casefold() in blob:
            bullets.append(f"подтверждает требование вакансии: {keyword}")
        if len(bullets) >= 2:
            break

    if any(token in blob for token in ("fastapi", "backend", "api", "sqlalchemy")):
        bullets.append("показывает backend/API опыт")
    if any(token in blob for token in ("workflow", "automation", "orchestration", "openai", "telegram")):
        bullets.append("показывает AI workflow automation")
    if any(token in blob for token in ("computer vision", "cv", "изображ", "video", "monitoring", "качества")):
        bullets.append("показывает проектный опыт с AI/CV monitoring")
    if any(token in blob for token in ("postgresql", "redis", "docker", "github", "repository")):
        bullets.append("подтверждает инженерную реализацию через проектные артефакты")

    if not bullets:
        bullets.append(_humanize_selection_reason(detail.get("reason")))

    deduped: list[str] = []
    for bullet in bullets:
        if bullet not in deduped:
            deduped.append(bullet)
    return deduped[:3]


def _document_focus(summary: dict[str, Any], detail_rows: list[dict[str, Any]]) -> str:
    blob = _text_blob(
        summary.get("matched_keywords"),
        summary.get("target_vacancy"),
        [item.get("title") for item in detail_rows],
        [item.get("skills") for item in detail_rows],
    )
    if any(token in blob for token in ("workflow", "automation", "orchestration", "openai")):
        return "вакансия сфокусирована на AI workflow automation"
    if any(token in blob for token in ("backend", "fastapi", "api")):
        return "вакансия сфокусирована на backend/API опыте"
    if "computer vision" in blob or "monitoring" in blob:
        return "вакансия сфокусирована на AI/CV monitoring"
    return "выбранные проекты ближе покрывают требования вакансии"


def _unused_reason(item: dict[str, Any], *, focus: str) -> str:
    blob = _text_blob(
        item.get("title"),
        item.get("snippet_text"),
        item.get("skills") or item.get("skills_json"),
        item.get("star_summary") or item.get("star_summary_json"),
    )
    fact_status = str(item.get("fact_status") or "").strip().lower()

    if fact_status in {"needs_confirmation", "unverified", "partial"}:
        return "факт ещё требует подтверждения перед использованием в сильном резюме"
    if fact_status == "rejected":
        return "факт отклонён и не должен попадать в документы"
    if "computer vision" in blob or "cv" in blob or "изображ" in blob or "video" in blob:
        if "workflow" in focus.casefold() or "backend" in focus.casefold():
            return focus
    if "analytics" in blob and ("workflow" in focus.casefold() or "backend" in focus.casefold()):
        return focus
    return "менее прямо поддерживает текущую вакансию, чем выбранные проекты"


def _document_picker_label(doc: ReviewDocumentDescriptor) -> str:
    kind_label = {
        "resume": "Резюме",
        "cover_letter": "Сопроводительное письмо",
    }.get(doc.document_kind, doc.document_kind)

    scope = "для текущей вакансии" if doc.vacancy_id else "без вакансии"
    parts = [f"{kind_label} {scope}"]

    if doc.review_status:
        parts.append(_humanize_review_status(doc.review_status))

    if doc.created_at:
        created_at = str(doc.created_at).strip()
        if len(created_at) >= 16:
            parts.append(f"{created_at[8:10]}.{created_at[5:7]} {created_at[11:16]}")
        else:
            parts.append(created_at)

    return " · ".join(part for part in parts if part)


def _format_readiness_score(score: Any) -> str:
    if score is None:
        return "—"
    try:
        return f"{round(float(score))} / 100"
    except (TypeError, ValueError):
        return str(score)


def _diff_item_prefix(section: str, kind: str) -> str:
    labels = {
        "skills": "навык",
        "matched_keywords": "ключевое слово",
        "summary_bullets": "пункт summary",
        "selected_achievements": "достижение",
        "claims_needing_confirmation": "утверждение, требующее подтверждения",
        "warnings": "предупреждение",
    }
    label = labels.get(section, section.replace("_", " "))

    if section == "claims_needing_confirmation" and kind == "added":
        return "⚠ Добавлено утверждение, требующее подтверждения:"
    if section == "warnings" and kind == "added":
        return "⚠ Добавлено предупреждение:"
    if kind == "added":
        return f"+ Добавлено {label}:"
    if kind == "removed":
        return f"- Удалено {label}:"
    if kind == "changed":
        return f"~ Обновлено {label}:"
    return f"{label}:"


def _resolve_document_diff_base_id(
    client: CareerCopilotApiClient,
    *,
    target_document_id: str,
    document_kind: str,
    vacancy_id: str | None,
    token: str | None,
) -> str | None:
    try:
        history = client.get_json(f"/documents/{target_document_id}/history", token=token)
    except Exception:
        return None

    items = history.get("items") if isinstance(history, dict) else []
    if isinstance(items, list):
        for item in items:
            if str(item.get("id") or "") != target_document_id:
                continue

            base_document_id = item.get("derived_from_id")
            if base_document_id:
                return str(base_document_id)
            break

    try:
        active_document = client.get_active_document(
            document_kind=document_kind,
            vacancy_id=vacancy_id,
            token=token,
        )
    except Exception:
        return None

    active_document_id = str(active_document.get("id") or "").strip()
    if active_document_id and active_document_id != target_document_id:
        return active_document_id

    return None


def _find_rationale_for_item(
    item_title: str,
    rationale_items: list[dict[str, Any]],
) -> str | None:
    normalized_title = item_title.strip().lower()
    for rationale in rationale_items:
        if str(rationale.get("item") or "").strip().lower() == normalized_title:
            reason = str(rationale.get("reason") or "").strip()
            if reason:
                return reason
    return None


def _render_readiness_panel(summary: dict[str, Any]) -> None:
    readiness = summary.get("readiness") or {}
    blockers = readiness.get("blockers") or []
    warnings = readiness.get("warnings") or []
    ready = bool(readiness.get("ready"))

    if ready:
        st.success("Готово к отправке ✅")
    elif blockers:
        st.error("Есть блокировка ❌")
    else:
        st.warning(
            "Не финализировано / требуется review. "
            "Критичных блокеров нет, поэтому документ можно использовать как draft."
        )

    col_ready, col_blockers, col_warnings, col_score = st.columns(4)

    with col_ready:
        st.metric("Готово", "Да" if ready else "Нет")
    with col_blockers:
        st.metric("Блокеры", len(blockers))
    with col_warnings:
        st.metric("Предупреждения", len(warnings))
    with col_score:
        st.metric("Оценка", _format_readiness_score(readiness.get("score")))

    if blockers:
        st.markdown("**Блокеры**")
        for blocker in blockers:
            st.markdown(f"- {blocker}")

    if warnings:
        st.markdown("**Предупреждения**")
        for warning in warnings:
            st.markdown(f"- {warning}")


def _confidence_label(score: int) -> str:
    if score >= 70:
        return "Высокая уверенность"
    if score >= 40:
        return "Средняя уверенность"
    return "Нужна осторожность"


def _confidence_item_label(value: Any) -> str:
    text = str(value or "").strip()
    lowered = text.casefold()
    if not text:
        return ""

    if "fastapi" in lowered or "backend" in lowered or "api" in lowered:
        return "backend/API опыт подтверждён"
    if any(token in lowered for token in ("workflow", "automation", "orchestration", "openai", "telegram")):
        return "AI workflow automation подтверждён"
    if any(token in lowered for token in ("computer vision", "cv", "monitoring", "изображ", "video")):
        return "AI/CV monitoring опыт подтверждён"
    if any(token in lowered for token in ("postgresql", "redis", "sqlalchemy", "database")):
        return "опыт работы с backend data layer подтверждён"
    if any(token in lowered for token in ("docker", "github", "repository", "git")):
        return "инженерные project artifacts подтверждены"
    return f"{text} подтверждён"


def _risk_item_label(value: Any) -> str:
    text = str(value or "").strip()
    lowered = text.casefold()
    if not text:
        return ""

    if any(token in lowered for token in ("kubernetes", "aws", "cloud", "docker", "deployment", "production")):
        return "production-scale infrastructure не подтверждена"
    if any(token in lowered for token in ("commercial", "enterprise", "prod", "production", "deployment")):
        return "commercial AI deployment experience не подтверждён"
    if any(token in lowered for token in ("leadership", "team lead", "management")):
        return "leadership/team ownership не подтверждён"
    if any(token in lowered for token in ("postgresql", "redis", "database")):
        return "глубина database/infra опыта требует проверки"
    return f"{text} не подтверждён"


def _render_confidence_risk_panel(summary: dict[str, Any]) -> None:
    matched_keywords = [
        str(item).strip()
        for item in (summary.get("matched_keywords") or [])
        if str(item).strip()
    ]
    missing_keywords = [
        str(item).strip()
        for item in (summary.get("missing_keywords") or [])
        if str(item).strip()
    ]
    selected_achievements = [
        item
        for item in (summary.get("selected_achievements") or [])
        if isinstance(item, dict)
    ]
    claims = summary.get("claims_needing_confirmation") or []
    readiness = summary.get("readiness") or {}
    warnings = list(readiness.get("warnings") or [])
    warnings.extend(summary.get("warnings") or [])

    confirmed_titles = [
        str(item.get("title") or item.get("name") or item.get("text") or "").strip()
        for item in selected_achievements
        if str(item.get("fact_status") or "").strip().lower()
        in {"confirmed", "user_provided"}
    ]
    confirmed_titles = [title for title in confirmed_titles if title]

    confidence_signals: list[str] = []
    for value in [*matched_keywords, *confirmed_titles]:
        label = _confidence_item_label(value)
        if label and label not in confidence_signals:
            confidence_signals.append(label)

    risk_signals: list[str] = []
    for value in missing_keywords:
        label = _risk_item_label(value)
        if label and label not in risk_signals:
            risk_signals.append(label)
    for claim in claims:
        if isinstance(claim, dict):
            claim_text = claim.get("text") or claim.get("claim_text") or claim.get("title")
        else:
            claim_text = claim
        label = _risk_item_label(claim_text)
        if label and label not in risk_signals:
            risk_signals.append(label)
    for warning in warnings:
        label = _risk_item_label(warning)
        if label and label not in risk_signals:
            risk_signals.append(label)

    readiness_score = readiness.get("score")
    try:
        score = int(float(readiness_score))
    except (TypeError, ValueError):
        score = min(100, len(confidence_signals) * 25)
        if risk_signals:
            score = max(0, score - min(40, len(risk_signals) * 10))

    st.markdown("### Уверенность и риски")
    st.caption(
        "Где система уверена в формулировках, а где лучше не делать сильные claims без проверки."
    )

    col_confidence, col_risk = st.columns(2)
    with col_confidence:
        st.markdown(f"#### {_confidence_label(score)}")
        if confidence_signals:
            for item in confidence_signals[:6]:
                st.markdown(f"✓ {item}")
        else:
            st.caption("Пока нет сильных подтверждённых сигналов.")

    with col_risk:
        st.markdown("#### Требует осторожности")
        if risk_signals:
            for item in risk_signals[:6]:
                st.markdown(f"⚠ {item}")
        else:
            st.success("Существенных overclaim-рисков не найдено.")


def _render_ai_changes_panel(diff: dict[str, Any]) -> None:
    sections = diff.get("sections") or []
    if not sections:
        st.caption("Структурных изменений не обнаружено.")
        return

    st.markdown("#### Обзор изменений")
    st.caption("Простой обзор: что добавлено, удалено или переписано между версиями.")

    grouped_lines = {"added": [], "removed": [], "changed": []}
    for section in sections:
        section_name = str(section.get("section") or "").strip()
        added = section.get("added") or []
        removed = section.get("removed") or []
        changed = section.get("changed") or []

        for item in added:
            grouped_lines["added"].append(f"{_diff_item_prefix(section_name, 'added')} {item}")
        for item in removed:
            grouped_lines["removed"].append(f"{_diff_item_prefix(section_name, 'removed')} {item}")
        for item in changed:
            grouped_lines["changed"].append(f"{_diff_item_prefix(section_name, 'changed')} {item}")

    if not any(grouped_lines.values()):
        st.caption("Структурных изменений не обнаружено.")
        return

    for title, key in (
        ("Добавлено", "added"),
        ("Удалено", "removed"),
        ("Переписано", "changed"),
    ):
        lines = grouped_lines[key]
        if not lines:
            continue
        with st.expander(f"{title} ({len(lines)})", expanded=key == "added"):
            for line in lines:
                st.markdown(f"- {line}")


def _render_claims_panel(summary: dict[str, Any]) -> None:
    claims = summary.get("claims_needing_confirmation") or []

    st.markdown("#### Утверждения, требующие подтверждения")
    if not claims:
        st.success("Утверждений, требующих подтверждения, нет.")
        return

    st.warning(f"{len(claims)} утверждений нужно подтвердить перед утверждением.")

    for claim in claims:
        claim_text = (
            claim.get("text")
            or claim.get("claim_text")
            or claim.get("title")
            or "Claim"
        )
        with st.container(border=True):
            st.write(claim_text)
            if claim.get("source"):
                st.caption(f"источник: {claim.get('source')}")
            if claim.get("fact_status"):
                st.caption(_fact_status_badge(str(claim.get("fact_status"))))


def _render_selected_achievements_panel(summary: dict[str, Any]) -> None:
    selected_achievements = summary.get("selected_achievements") or []
    rationale_items = summary.get("selection_rationale") or []

    st.markdown("#### Выбранные достижения")
    if not selected_achievements:
        st.caption("Выбранных достижений нет.")
        return

    for item in selected_achievements:
        title = (
            item.get("title")
            or item.get("name")
            or item.get("text")
            or "Achievement"
        )
        reason = _find_rationale_for_item(title, rationale_items)
        fact_status = item.get("fact_status")

        with st.container(border=True):
            st.markdown(f"**{title}**")
            if fact_status:
                st.caption(_fact_status_badge(str(fact_status)))
            metric_text = item.get("metric_text") or item.get("impact") or item.get("result")
            if metric_text:
                st.write(metric_text)
            if reason:
                st.caption(f"Почему выбрано: {_humanize_selection_reason(reason)}")


def _render_evidence_used_panel(
    client: CareerCopilotApiClient,
    *,
    summary: dict[str, Any],
    token: str | None,
) -> None:
    selected_evidence_ids = [
        str(value).strip()
        for value in (summary.get("selected_evidence_ids") or [])
        if str(value).strip()
    ]
    if not selected_evidence_ids:
        st.markdown("#### Использованные доказательства")
        st.caption("Для этого документа пока не привязаны подтверждённые доказательства.")
        return

    selected_achievements = summary.get("selected_achievements") or []
    rationale_items = summary.get("evidence_selection_reason") or []
    achievements_by_id = {
        str(item.get("id") or "").strip(): item
        for item in selected_achievements
        if str(item.get("id") or "").strip()
    }

    rows: list[dict[str, Any]] = []
    detail_rows: list[dict[str, Any]] = []
    for evidence_id in selected_evidence_ids:
        achievement = achievements_by_id.get(evidence_id, {})
        title = (
            achievement.get("title")
            or achievement.get("text")
            or achievement.get("name")
            or "Подтверждённый опыт"
        )
        reason = str(achievement.get("reason") or "").strip()
        if not reason:
            reason = _find_rationale_for_item(str(title), rationale_items) or "—"

        fact_status = str(achievement.get("fact_status") or "").strip() or "—"
        rows.append(
            {
                "Опыт": title,
                "Почему выбран": _humanize_selection_reason(reason),
                "Статус": _fact_status_badge(fact_status),
            }
        )

        detail_row: dict[str, Any] = {
            "evidence_id": evidence_id,
            "title": title,
            "reason": reason,
        }
        try:
            snippet = client.get_evidence_snippet(evidence_id, token=token)
        except Exception as exc:
            detail_row["lookup_error"] = str(exc)
        else:
            detail_row["evidence_strength"] = snippet.get("evidence_strength") or "—"
            detail_row["fact_status"] = snippet.get("fact_status") or fact_status
            detail_row["usage_count"] = snippet.get("usage_count", 0)
            detail_row["used_in_documents_count"] = snippet.get("used_in_documents_count", 0)
            detail_row["used_in_interviews_count"] = snippet.get("used_in_interviews_count", 0)
            detail_row["snippet_text"] = snippet.get("snippet_text") or ""
            detail_row["skills"] = snippet.get("skills") or snippet.get("skills_json") or []
            star_summary = snippet.get("star_summary") or snippet.get("star_summary_json") or {}
            if isinstance(star_summary, dict):
                detail_row["star_summary"] = star_summary
        detail_rows.append(detail_row)

    st.markdown("#### Использованные доказательства")
    st.caption("Опыт, который система реально использовала при подготовке документа.")
    st.dataframe(rows, width="stretch", hide_index=True)

    st.markdown("#### Почему эти проекты попали в резюме")
    matched_keywords = summary.get("matched_keywords") or []
    for detail in detail_rows:
        with st.container(border=True):
            st.markdown(f"**{detail.get('title') or 'Подтверждённый опыт'}**")
            for bullet in _project_fit_bullets(
                detail=detail,
                matched_keywords=matched_keywords,
            ):
                st.markdown(f"✓ {bullet}")

    focus = _document_focus(summary, detail_rows)
    try:
        all_snippets = client.list_evidence_snippets(token=token)
    except Exception:
        all_snippets = []

    selected_ids = set(selected_evidence_ids)
    unused_rows = [
        item
        for item in all_snippets
        if isinstance(item, dict)
        and str(item.get("id") or "").strip()
        and str(item.get("id") or "").strip() not in selected_ids
    ]

    st.markdown("#### Что не было использовано")
    if not unused_rows:
        st.caption("Неприменённых проектных доказательств для этого документа не найдено.")
    else:
        for item in unused_rows[:5]:
            title = item.get("title") or "Подтверждающий опыт"
            st.markdown(f"- **{title}**")
            st.caption(f"Причина: {_unused_reason(item, focus=focus)}")

    with st.expander("Почему система так решила", expanded=False):
        for detail in detail_rows:
            with st.container(border=True):
                st.markdown(f"**{detail.get('title') or 'Подтверждённый опыт'}**")
                st.caption(
                    "Почему это считается релевантным: "
                    f"{_humanize_selection_reason(detail.get('reason'))}"
                )

                if detail.get("lookup_error"):
                    st.warning(f"Не удалось загрузить детали доказательства: {detail.get('lookup_error')}")
                    continue

                st.caption(
                    " / ".join(
                        part
                        for part in [
                            _fact_status_badge(str(detail.get("fact_status"))),
                            _humanize_evidence_strength(detail.get("evidence_strength")),
                            f"использований: {detail.get('usage_count', 0)}",
                        ]
                        if part
                    )
                )

                star_summary = detail.get("star_summary") or {}
                if isinstance(star_summary, dict) and star_summary:
                    st.caption(
                        "STAR: "
                        + ", ".join(
                            f"{key}={value}"
                            for key, value in star_summary.items()
                            if value not in (None, "", [])
                        )
                    )

                snippet_text = str(detail.get("snippet_text") or "").strip()
                if snippet_text:
                    st.write(snippet_text)


def _render_keywords_panel(summary: dict[str, Any]) -> None:
    matched_keywords = summary.get("matched_keywords") or []
    missing_keywords = summary.get("missing_keywords") or []

    st.markdown("#### Покрытие ключевых слов")
    col_matched, col_missing = st.columns(2)

    with col_matched:
        st.markdown("**Совпавшие ключевые слова**")
        if matched_keywords:
            for keyword in matched_keywords:
                st.markdown(f"- {keyword}")
        else:
            st.caption("—")

    with col_missing:
        st.markdown("**Отсутствующие ключевые слова**")
        if missing_keywords:
            for keyword in missing_keywords:
                st.markdown(f"- {keyword}")
        else:
            st.caption("—")


def _render_final_preview_panel(document: dict[str, Any], *, key_suffix: str) -> None:
    rendered_text = document.get("rendered_text") or ""
    document_id = str(document.get("id") or "").strip() or "document"
    st.markdown("#### Итоговый предпросмотр")
    if not rendered_text.strip():
        st.caption("rendered_text пока недоступен.")
        return

    st.text_area(
        "Отрендеренный текст",
        value=rendered_text,
        height=420,
        disabled=True,
        key=f"document_review_preview_{key_suffix}_{document_id}",
    )


def _render_export_controls(
    client: CareerCopilotApiClient,
    *,
    document_id: str,
    document_kind: str,
    token: str | None,
    key_suffix: str,
) -> None:
    document_label = _humanize_document_kind(document_kind)
    safe_kind = document_kind.replace("_", "-") or "document"
    export_specs = [
        ("txt", f"Экспорт {document_label} TXT", "text/plain", "txt", client.get_text),
        ("md", f"Экспорт {document_label} MD", "text/markdown", "md", client.get_text),
        (
            "docx",
            f"Экспорт {document_label} DOCX",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "docx",
            client.get_bytes,
        ),
    ]

    cols = st.columns(3)
    for column, (export_format, label, mime, extension, getter) in zip(cols, export_specs, strict=False):
        with column:
            try:
                content = getter(
                    f"/documents/{document_id}/export/{export_format}",
                    token=token,
                )
            except Exception as exc:
                st.caption(f"{label} недоступен: {exc}")
                continue

            st.download_button(
                label,
                data=content,
                file_name=f"{safe_kind}-{document_id}.{extension}",
                mime=mime,
                width="stretch",
                key=f"document_review_export_{document_kind}_{export_format}_{key_suffix}_{document_id}",
            )


def _render_workflow_selection_status() -> None:
    resume_ready = bool(st.session_state.get("approved_resume"))
    cover_letter_ready = bool(st.session_state.get("approved_cover_letter"))

    if resume_ready and cover_letter_ready:
        st.success("Оба документа выбраны. Можно переходить к шагу 10.")
        return

    missing = []
    if not resume_ready:
        missing.append("резюме")
    if not cover_letter_ready:
        missing.append("сопроводительное письмо")

    st.info(
        "Для продолжения workflow ещё нужно выбрать: "
        + ", ".join(missing)
    )


def _return_to_document_selector(selection_state_key: str | None, document_kind: str) -> None:
    if not selection_state_key:
        return
    st.session_state.pop(selection_state_key, None)
    st.session_state.pop(f"{selection_state_key}_picker", None)
    if document_kind == "resume" and not st.session_state.get("approved_cover_letter"):
        st.session_state[f"{selection_state_key}_preferred_kind"] = "cover_letter"
    elif document_kind == "cover_letter" and not st.session_state.get("approved_resume"):
        st.session_state[f"{selection_state_key}_preferred_kind"] = "resume"
    st.session_state["document_review_step9_return_notice"] = True


def _sync_generated_document_state(document_kind: str, approved_document: dict[str, Any]) -> None:
    state_key = (
        "generated_resume"
        if document_kind == "resume"
        else "generated_cover_letter"
        if document_kind == "cover_letter"
        else None
    )
    if not state_key:
        return

    current_value = st.session_state.get(state_key)
    if not isinstance(current_value, dict):
        return

    current_id = str(current_value.get("document_id") or current_value.get("id") or "").strip()
    approved_id = str(approved_document.get("document_id") or approved_document.get("id") or "").strip()
    if current_id != approved_id:
        return

    st.session_state[state_key] = {
        **current_value,
        "review_status": approved_document.get("review_status", current_value.get("review_status")),
        "is_active": approved_document.get("is_active", current_value.get("is_active")),
        "updated_at": approved_document.get("updated_at", current_value.get("updated_at")),
    }


def _render_action_bar(
    client: CareerCopilotApiClient,
    *,
    document: dict[str, Any],
    token: str | None,
    selection_state_key: str | None,
) -> None:
    document_id = str(document.get("id") or "").strip()
    document_kind = str(document.get("document_kind") or "").strip()
    rendered_text = document.get("rendered_text") or ""
    key_suffix = f"{selection_state_key or 'document'}_{document_id}"

    if not document_id:
        st.warning("Не удалось определить документ, панель действий недоступна.")
        return

    st.caption(
        "Чтобы продолжить workflow, нужно отдельно выбрать "
        "резюме и сопроводительное письмо."
    )

    col_approve, col_enhance, col_back = st.columns(3)

    with col_approve:
        approve_clicked = st.button(
            "Утвердить",
            type="primary",
            width="stretch",
            disabled=str(document.get("review_status") or "") == "approved",
            key=f"document_review_approve_{key_suffix}",
        )

        use_draft_clicked = st.button(
            "Использовать как draft",
            width="stretch",
            help=(
                "Не утверждает документ как финальный. "
                "Позволяет продолжить workflow, а отклик будет помечен как review_required."
            ),
            key=f"document_review_use_draft_{key_suffix}",
        )

    with col_enhance:
        enhance_clicked = st.button(
            "Создать улучшенную версию",
            width="stretch",
            key=f"document_review_enhance_{key_suffix}",
        )

    with col_back:
        back_clicked = st.button(
            "Назад",
            width="stretch",
            disabled=selection_state_key is None,
            key=f"document_review_back_{key_suffix}",
        )

    if approve_clicked:
        try:
            approved_document = client.patch_json(
                f"/documents/{document_id}/review",
                {
                    "review_status": "approved",
                    "review_comment": "Approved via Document Review Workspace",
                    "set_active_when_approved": True,
                },
                token=token,
            )
        except Exception as exc:
            st.error(f"Не удалось утвердить: {exc}")
        else:
            if isinstance(approved_document, dict):
                if document_kind == "resume":
                    st.session_state["approved_resume"] = approved_document
                elif document_kind == "cover_letter":
                    st.session_state["approved_cover_letter"] = approved_document
                _sync_generated_document_state(document_kind, approved_document)
                if selection_state_key:
                    st.session_state[selection_state_key] = document_id
                st.session_state["application"] = None
                st.session_state["interview_session"] = None
                st.session_state["interview_answers_result"] = None
                st.success("Документ утверждён. Экспорт доступен ниже.")
                _render_workflow_selection_status()
            st.rerun()

    if use_draft_clicked:
        document_payload = {
            "document_id": document_id,
            "review_status": "draft",
            "used_as_draft": True,
            "requires_human_review": True,
        }

        if document_kind == "resume":
            st.session_state["approved_resume"] = document_payload
        elif document_kind == "cover_letter":
            st.session_state["approved_cover_letter"] = document_payload

        st.session_state["application"] = None
        st.session_state["interview_session"] = None
        st.session_state["interview_answers_result"] = None

        st.success("Документ выбран как draft. Отклик будет создан с пометкой review_required.")
        _render_workflow_selection_status()
        _return_to_document_selector(selection_state_key, document_kind)
        st.rerun()

    if enhance_clicked:
        if document_kind == "resume":
            payload = {"resume_text": rendered_text}
            path = f"/documents/resumes/{document_id}/enhance"
        elif document_kind == "cover_letter":
            payload = {"cover_letter_text": rendered_text}
            path = f"/documents/letters/{document_id}/enhance"
        else:
            st.error(f"Неподдерживаемый document_kind для улучшения: {document_kind}")
            return

        try:
            enhanced_document = client.post_json(path, payload, token=token)
        except Exception as exc:
            st.error(f"Не удалось создать улучшенную версию: {exc}")
            return

        next_document_id = str(enhanced_document.get("document_id") or "").strip()
        if next_document_id and selection_state_key:
            st.session_state[selection_state_key] = next_document_id

        st.session_state["approved_resume"] = None
        st.session_state["approved_cover_letter"] = None
        st.session_state["application"] = None
        st.session_state["interview_session"] = None
        st.session_state["interview_answers_result"] = None

        st.success("Улучшенная версия создана")
        st.rerun()

    if back_clicked and selection_state_key:
        st.session_state.pop(selection_state_key, None)
        st.session_state.pop(f"{selection_state_key}_picker", None)
        st.rerun()

    st.markdown("### Экспорт")
    _render_export_controls(
        client,
        document_id=document_id,
        document_kind=document_kind,
        token=token,
        key_suffix=selection_state_key or "document",
    )


def render_document_review_workspace(
    client: CareerCopilotApiClient,
    *,
    document_id: str,
    title: str,
    document_kind: str,
    vacancy_id: str | None,
    token: str | None,
    selection_state_key: str | None = None,
) -> None:
    if not client.has_entity_id(document_id):
        st.warning("Документ ещё не выбран для review-summary.")
        return

    try:
        document = client.get_document_version(document_id, token=token)
    except Exception as exc:
        st.error(f"Не удалось загрузить документ: {exc}")
        return

    try:
        summary = client.get_document_review_summary(document_id, token=token)
    except Exception as exc:
        st.error(f"Не удалось загрузить review-summary: {exc}")
        summary = {}

    base_document_id = _resolve_document_diff_base_id(
        client,
        target_document_id=document_id,
        document_kind=document_kind,
        vacancy_id=vacancy_id,
        token=token,
    )

    diff: dict[str, Any] = {}
    if base_document_id:
        try:
            diff = client.get_document_diff(
                base_document_id=base_document_id,
                target_document_id=document_id,
                token=token,
            )
        except Exception as exc:
            st.caption(f"Структурный diff недоступен: {exc}")

    st.markdown(f"## Документ: {title}")
    st.caption(
        f"Версия: {document.get('version_label') or '—'} · "
        f"Статус: {_humanize_review_status(document.get('review_status'))} · "
        f"Тип: {_humanize_document_kind(str(document.get('document_kind') or document_kind))}"
    )

    readiness = summary.get("readiness") or {}
    st.markdown("### Панель готовности")
    _render_readiness_panel(summary)

    st.divider()
    _render_confidence_risk_panel(summary)

    st.divider()
    st.markdown("### Панель изменений ИИ")
    _render_ai_changes_panel(diff)

    st.divider()
    _render_claims_panel(summary)

    st.divider()
    _render_selected_achievements_panel(summary)

    st.divider()
    _render_evidence_used_panel(client, summary=summary, token=token)

    st.divider()
    _render_keywords_panel(summary)

    st.divider()
    _render_final_preview_panel(document, key_suffix=selection_state_key or "document")

    st.divider()
    st.markdown("### Панель действий")
    _render_action_bar(
        client,
        document=document,
        token=token,
        selection_state_key=selection_state_key,
    )


def render_document_review_workspace_selector(
    client: CareerCopilotApiClient,
    *,
    documents: list[ReviewDocumentDescriptor],
    token: str | None,
    selection_state_key: str,
) -> None:
    available_documents = [doc for doc in documents if doc.document_id]
    if not available_documents:
        st.info("Пока нет документов для проверки.")
        return

    options = [doc.document_id for doc in available_documents]
    labels = {
        doc.document_id: _document_picker_label(doc)
        for doc in available_documents
    }

    selected_document_id = st.session_state.get(selection_state_key)
    if selected_document_id not in options:
        preferred_kind = st.session_state.pop(f"{selection_state_key}_preferred_kind", None)
        preferred_document = next(
            (
                doc for doc in available_documents
                if preferred_kind and doc.document_kind == preferred_kind
            ),
            None,
        )
        selected_document_id = (
            preferred_document.document_id
            if preferred_document is not None
            else options[0]
        )

    selected_document_id = st.selectbox(
        "Выберите документ",
        options=options,
        index=options.index(selected_document_id),
        format_func=lambda value: labels.get(value, value),
        key=f"{selection_state_key}_picker",
    )
    st.session_state[selection_state_key] = selected_document_id

    selected_document = next(
        (doc for doc in available_documents if doc.document_id == selected_document_id),
        available_documents[0],
    )

    st.caption(
        "Здесь собраны готовность, структурный diff, утверждения для подтверждения, "
        "покрытие ключевых слов, предпросмотр и действия."
    )

    render_document_review_workspace(
        client,
        document_id=selected_document.document_id,
        title=selected_document.title,
        document_kind=selected_document.document_kind,
        vacancy_id=selected_document.vacancy_id,
        token=token,
        selection_state_key=selection_state_key,
    )


def render_document_review_workspace_tab(
    client: CareerCopilotApiClient,
    *,
    token: str | None = None,
    selection_state_key: str = "document_review_workspace_tab_selection",
    current_vacancy_id: str | None = None,
    show_only_current_vacancy: bool = False,
) -> None:
    st.header("Проверка документов")
    st.caption(
        "Рабочая область для проверки одного документа: подтверждение, "
        "навигация между документами и создание версий."
    )

    if not token:
        st.warning("Войдите, чтобы проверять и подтверждать документы.")
        return

    documents: list[ReviewDocumentDescriptor] = []
    diagnostics: dict[str, Any] = {}
    active_documents: dict[str, Any] = {}
    current_application: dict[str, Any] = {}

    if token:
        try:
            diagnostics = client.get_system_health_diagnostics(token=token)
        except Exception:
            diagnostics = {}
        if isinstance(diagnostics, dict):
            active_documents = diagnostics.get("active_documents") or {}
            current_application = diagnostics.get("current_active_application") or {}

    generated_resume = st.session_state.get("generated_resume")
    if generated_resume and generated_resume.get("document_id"):
        documents.append(
            ReviewDocumentDescriptor(
                document_id=str(generated_resume["document_id"]),
                title="Tailored Resume",
                document_kind=str(generated_resume.get("document_kind") or "resume"),
                vacancy_id=str(generated_resume.get("vacancy_id") or "") or None,
            )
        )

    generated_cover_letter = st.session_state.get("generated_cover_letter")
    if generated_cover_letter and generated_cover_letter.get("document_id"):
        documents.append(
            ReviewDocumentDescriptor(
                document_id=str(generated_cover_letter["document_id"]),
                title="Cover Letter",
                document_kind=str(generated_cover_letter.get("document_kind") or "cover_letter"),
                vacancy_id=str(generated_cover_letter.get("vacancy_id") or "") or None,
            )
        )

    seen_document_ids = {doc.document_id for doc in documents if doc.document_id}
    for document_kind, title in (
        ("resume", "Резюме"),
        ("cover_letter", "Сопроводительное письмо"),
    ):
        source_document = active_documents.get(document_kind)
        if not isinstance(source_document, dict):
            continue

        document_id = str(source_document.get("id") or source_document.get("document_id") or "").strip()
        if not document_id or document_id in seen_document_ids:
            continue

        seen_document_ids.add(document_id)
        documents.append(
            ReviewDocumentDescriptor(
                document_id=document_id,
                title=title,
                document_kind=str(source_document.get("document_kind") or document_kind),
                vacancy_id=str(source_document.get("vacancy_id") or "") or None,
            )
        )

    if not documents:
        vacancy_id = None
        if isinstance(current_application, dict):
            vacancy_id = str(current_application.get("vacancy_id") or "").strip() or None

        for document_kind, title in (
            ("resume", "Резюме"),
            ("cover_letter", "Сопроводительное письмо"),
        ):
            try:
                active_document = client.get_active_document(
                    document_kind=document_kind,
                    vacancy_id=vacancy_id,
                    token=token,
                )
            except Exception:
                continue

            document_id = str(active_document.get("id") or "").strip()
            if not document_id:
                continue

            documents.append(
                ReviewDocumentDescriptor(
                    document_id=document_id,
                    title=title,
                    document_kind=str(active_document.get("document_kind") or document_kind),
                    vacancy_id=str(active_document.get("vacancy_id") or "") or None,
                )
            )

    if show_only_current_vacancy and current_vacancy_id:
        documents = [
            doc
            for doc in documents
            if str(doc.vacancy_id or "") == str(current_vacancy_id)
        ]

    if not documents:
        st.info("Пока нет документов, готовых к проверке.")
        return

    render_document_review_workspace_selector(
        client,
        documents=documents,
        token=token,
        selection_state_key=selection_state_key,
    )
