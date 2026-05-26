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

    if readiness.get("ready"):
        st.success("Готово к отправке ✅")
    else:
        st.error("Есть блокировка ❌")

    col_ready, col_blockers, col_warnings, col_score = st.columns(4)

    with col_ready:
        st.metric("Готово", "Да" if readiness.get("ready") else "Нет")
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


def _render_ai_changes_panel(diff: dict[str, Any]) -> None:
    sections = diff.get("sections") or []
    if not sections:
        st.caption("Структурных изменений не обнаружено.")
        return

    st.markdown("#### Изменения ИИ")
    st.caption("Структурный diff на основе `content_json[\"sections\"]`.")

    rendered_lines: list[str] = []
    for section in sections:
        section_name = str(section.get("section") or "").strip()
        added = section.get("added") or []
        removed = section.get("removed") or []
        changed = section.get("changed") or []

        for item in added:
            rendered_lines.append(f"{_diff_item_prefix(section_name, 'added')} {item}")
        for item in removed:
            rendered_lines.append(f"{_diff_item_prefix(section_name, 'removed')} {item}")
        for item in changed:
            rendered_lines.append(f"{_diff_item_prefix(section_name, 'changed')} {item}")

    if not rendered_lines:
        st.caption("Структурных изменений не обнаружено.")
        return

    for line in rendered_lines:
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
                st.caption(f"статус факта: {claim.get('fact_status')}")


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
                st.caption(f"статус факта: {fact_status}")
            metric_text = item.get("metric_text") or item.get("impact") or item.get("result")
            if metric_text:
                st.write(metric_text)
            if reason:
                st.caption(f"почему выбрано: {reason}")


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
        st.caption("Backend не вернул выбранные ID доказательств.")
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
            or evidence_id
        )
        reason = str(achievement.get("reason") or "").strip()
        if not reason:
            reason = _find_rationale_for_item(str(title), rationale_items) or "—"

        fact_status = str(achievement.get("fact_status") or "").strip() or "—"
        rows.append(
            {
                "Evidence ID": evidence_id,
                "Title": title,
                "Reason": reason,
                "Fact status": fact_status,
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
            star_summary = snippet.get("star_summary") or snippet.get("star_summary_json") or {}
            if isinstance(star_summary, dict):
                detail_row["star_summary"] = star_summary
        detail_rows.append(detail_row)

    st.markdown("#### Использованные доказательства")
    st.caption("ID и причины выбора приходят из `content_json.meta`.")
    st.dataframe(rows, use_container_width=True, hide_index=True)

    with st.expander("Детали доказательств", expanded=False):
        for detail in detail_rows:
            with st.container(border=True):
                st.markdown(f"**{detail.get('title') or detail.get('evidence_id')}**")
                st.caption(f"evidence_id: {detail.get('evidence_id')}")
                st.caption(f"причина: {detail.get('reason')}")

                if detail.get("lookup_error"):
                    st.warning(f"Не удалось загрузить детали сниппета: {detail.get('lookup_error')}")
                    continue

                st.caption(
                    " / ".join(
                        part
                        for part in [
                            f"статус факта: {detail.get('fact_status')}",
                            f"сила: {detail.get('evidence_strength')}",
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
    token: str | None,
    key_suffix: str,
) -> None:
    try:
        txt_content = client.get_text(f"/documents/{document_id}/export/txt", token=token)
        md_content = client.get_text(f"/documents/{document_id}/export/md", token=token)
        docx_content = client.get_bytes(f"/documents/{document_id}/export/docx", token=token)
    except Exception as exc:
        st.error(f"Экспорт недоступен: {exc}")
        return

    col_txt, col_md, col_docx = st.columns(3)
    with col_txt:
        st.download_button(
            "Экспорт TXT",
            data=txt_content,
            file_name=f"{document_id}.txt",
            mime="text/plain",
            use_container_width=True,
            key=f"document_review_export_txt_{key_suffix}_{document_id}",
        )
    with col_md:
        st.download_button(
            "Экспорт MD",
            data=md_content,
            file_name=f"{document_id}.md",
            mime="text/markdown",
            use_container_width=True,
            key=f"document_review_export_md_{key_suffix}_{document_id}",
        )
    with col_docx:
        st.download_button(
            "Экспорт DOCX",
            data=docx_content,
            file_name=f"{document_id}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
            key=f"document_review_export_docx_{key_suffix}_{document_id}",
        )


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
        st.warning("Не указан ID документа, панель действий недоступна.")
        return

    col_approve, col_enhance, col_back = st.columns(3)

    with col_approve:
        approve_clicked = st.button(
            "Утвердить",
            type="primary",
            use_container_width=True,
            disabled=str(document.get("review_status") or "") == "approved",
            key=f"document_review_approve_{key_suffix}",
        )

    with col_enhance:
        enhance_clicked = st.button(
            "Создать улучшенную версию",
            use_container_width=True,
            key=f"document_review_enhance_{key_suffix}",
        )

    with col_back:
        back_clicked = st.button(
            "Назад",
            use_container_width=True,
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
                st.session_state["application"] = None
                st.session_state["interview_session"] = None
                st.session_state["interview_answers_result"] = None
                st.success("Документ утверждён")
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
            st.session_state[f"{selection_state_key}_picker"] = next_document_id

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
    _render_export_controls(client, document_id=document_id, token=token, key_suffix=selection_state_key or "document")


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
        doc.document_id: f"{doc.title} · {doc.document_kind} · {doc.document_id[:8]}"
        for doc in available_documents
    }

    selected_document_id = st.session_state.get(selection_state_key)
    if selected_document_id not in options:
        selected_document_id = options[0]

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
) -> None:
    st.header("Проверка документов")
    st.caption(
        "Рабочая область для проверки одного документа: подтверждение, "
        "fallback-навигация и создание версий."
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
                title=f"{title} · {document_id[:8]}",
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

    if not documents:
        st.info("Пока нет документов, готовых к проверке.")
        return

    render_document_review_workspace_selector(
        client,
        documents=documents,
        token=token,
        selection_state_key=selection_state_key,
    )
