# frontend\streamlit\flows\vacancy_flow.py

from __future__ import annotations

import re

import httpx
import streamlit as st

from api_client import CareerCopilotApiClient


def _reset_downstream_vacancy_state() -> None:
    for key in [
        "generated_resume",
        "generated_cover_letter",
        "application",
        "interview_session",
        "interview_answers_result",
    ]:
        st.session_state[key] = None

    for key in [
        "document_review_workspace_step9_selection",
        "document_review_workspace_step9_selection_picker",
        "document_review_workspace_tab_selection",
        "document_review_workspace_tab_selection_picker",
        "approved_resume",
        "approved_cover_letter",
    ]:
        st.session_state.pop(key, None)


def _vacancy_source_label(source: str | None) -> str:
    normalized = str(source or "").strip().lower()
    if normalized == "hh":
        return "HH"
    if normalized == "file":
        return "Файл"
    if normalized == "manual":
        return "Ручной ввод"
    return str(source or "—")


def _humanize_fact_status(value: object) -> str:
    status = str(value or "").strip().lower()
    return {
        "confirmed": "Подтверждено пользователем",
        "user_provided": "Есть в резюме/профиле",
        "needs_confirmation": "Требует подтверждения",
        "partial": "Подтверждено частично",
        "rejected": "Отклонено",
        "unverified": "Требует проверки",
    }.get(status, "Требует проверки")


def _humanize_strength(value: object) -> str:
    strength = str(value or "").strip().lower()
    return {
        "strong": "сильное подтверждение",
        "medium": "частичное подтверждение",
        "weak": "слабое подтверждение",
    }.get(strength, "требует проверки")


def _humanize_requirement_reason(reason: object) -> str:
    text = str(reason or "").strip()
    if not text or text == "—":
        return "Система сопоставила требование вакансии с подтверждённым опытом."

    confirmed = re.match(r"Confirmed evidence found:\s*(.+?)\s*\(([^,]+),\s*([^)]+)\)\.", text)
    partial = re.match(r"Partial evidence found:\s*(.+?)\s*\(([^,]+),\s*([^)]+)\)\.", text)
    if confirmed or partial:
        match = confirmed or partial
        title = match.group(1)
        strength = _humanize_strength(match.group(2))
        status = _humanize_fact_status(match.group(3))
        prefix = "Почему система считает это подтверждённым"
        if partial:
            prefix = "Почему система считает это частично подтверждённым"
        return f"{prefix}: {title} — {strength}, {status}."

    if text == "No matching confirmed evidence found.":
        return "Подтверждённого опыта по этому требованию пока не найдено."

    return text


def _render_fit_summary(coverage: dict) -> None:
    strong = coverage.get("strong") or []
    medium = coverage.get("medium") or []
    missing = coverage.get("missing") or []

    st.markdown("#### Почему система считает вас релевантным")
    if not strong and not medium and not missing:
        st.caption("Сопоставление с доказательствами пока недоступно.")
        return

    for item in strong[:4]:
        st.markdown(f"✓ Есть подтверждённый опыт: {item.get('requirement') or 'требование вакансии'}")
    for item in medium[:3]:
        st.markdown(f"⚠ Требует дополнительного подтверждения: {item.get('requirement') or 'требование вакансии'}")
    for item in missing[:3]:
        st.markdown(f"✕ Нет подтверждённого опыта: {item.get('requirement') or 'требование вакансии'}")


def _render_vacancy_import_status(notice: dict) -> None:
    st.success("✅ Вакансия успешно импортирована")
    st.markdown(f"**Источник:** {_vacancy_source_label(notice.get('source'))}")
    st.markdown(f"**Название:** {notice.get('title') or '—'}")
    st.markdown(f"**Компания:** {notice.get('company') or '—'}")
    st.markdown(f"**Длина текста:** {notice.get('description_length') or 0}")

    with st.expander("Технические детали", expanded=False):
        st.caption(f"vacancy_id: {notice.get('vacancy_id') or '—'}")


def _render_hh_vacancy_import(client: CareerCopilotApiClient, token: str | None) -> None:
    st.markdown("#### Быстрый импорт по ссылке HH")

    hh_source_url = st.text_input(
        "Ссылка на вакансию HH",
        value="",
        placeholder="https://barnaul.hh.ru/vacancy/133412268",
        key="hh_vacancy_import_url",
    )

    if st.button("Загрузить вакансию по ссылке HH", type="primary", use_container_width=True):
        if not hh_source_url.strip():
            st.error("Вставьте ссылку на вакансию HH.")
        else:
            try:
                result = client.import_vacancy_from_url(
                    source_url=hh_source_url.strip(),
                    token=token,
                )
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in {502, 504}:
                    st.warning(
                        "⚠ HH не отдал вакансию автоматически. "
                        "Это может быть ограничение HH, сети backend или временная недоступность."
                    )
                    st.info(
                        "Скопируйте текст вакансии и вставьте его в ручную форму ниже "
                        "или загрузите вакансию из файла."
                    )
                    st.code(exc.response.text)
                else:
                    st.error(f"Backend вернул ошибку HTTP {exc.response.status_code}")
                    st.code(exc.response.text)
            except httpx.TimeoutException as exc:
                st.error(
                    "Импорт вакансии с HH не успел завершиться. "
                    "Попробуйте ещё раз или вставьте текст вакансии вручную ниже."
                )
                st.code(str(exc))
            except httpx.RequestError as exc:
                st.error("Не удалось подключиться к backend")
                st.code(str(exc))
            except ValueError as exc:
                st.error("Backend вернул неожиданный ответ")
                st.code(str(exc))
            else:
                if not isinstance(result, dict):
                    st.error("Backend вернул неожиданный формат ответа")
                    st.json(result)
                else:
                    st.session_state.vacancy = result
                    st.session_state.vacancy_import_notice = {
                        "message": "Вакансия успешно импортирована",
                        "vacancy_id": result.get("vacancy_id") or result.get("id"),
                        "title": result.get("title"),
                        "company": result.get("company"),
                        "source": result.get("source"),
                        "description_length": result.get("description_length"),
                    }
                    st.session_state.vacancy_analysis = None
                    _reset_downstream_vacancy_state()
                    st.success("✅ Вакансия успешно импортирована")
                    st.rerun()


def _render_file_vacancy_import(client: CareerCopilotApiClient, token: str | None) -> None:
    st.markdown("#### Импорт вакансии из файла")

    uploaded_vacancy_file = st.file_uploader(
        "Выберите файл вакансии",
        type=["txt", "pdf", "docx"],
        help="Можно загрузить TXT, PDF или DOCX с текстом вакансии.",
        key="vacancy_file_uploader",
    )

    file_title = st.text_input(
        "Название вакансии из файла",
        value="",
        key="vacancy_file_title",
    )
    file_company = st.text_input(
        "Компания из файла",
        value="",
        key="vacancy_file_company",
    )
    file_location = st.text_input(
        "Локация из файла",
        value="",
        key="vacancy_file_location",
    )
    file_source_url = st.text_input(
        "Ссылка на источник файла",
        value="",
        key="vacancy_file_source_url",
        help="Опционально.",
    )

    if uploaded_vacancy_file is not None:
        st.caption(f"Файл: {uploaded_vacancy_file.name}")
        st.caption(f"Тип: {uploaded_vacancy_file.type or 'не определён'}")
        st.caption(f"Размер: {uploaded_vacancy_file.size} байт")

    if st.button("Импортировать вакансию из файла", type="primary", use_container_width=True):
        if uploaded_vacancy_file is None:
            st.error("Выберите файл вакансии.")
            return

        try:
            uploaded_source_file = client.upload_file(
                path="/files/upload",
                file_kind="vacancy",
                filename=uploaded_vacancy_file.name,
                content=uploaded_vacancy_file.getvalue(),
                content_type=uploaded_vacancy_file.type or "application/octet-stream",
                token=token,
            )
            result = client.import_vacancy_from_file(
                source_file_id=str(uploaded_source_file.get("id")),
                title=file_title.strip() or None,
                company=file_company.strip() or None,
                location=file_location.strip() or None,
                source_url=file_source_url.strip() or None,
                token=token,
            )
        except httpx.HTTPStatusError as exc:
            st.error(f"Backend вернул ошибку HTTP {exc.response.status_code}")
            st.code(exc.response.text)
            return
        except httpx.RequestError as exc:
            st.error("Не удалось подключиться к backend")
            st.code(str(exc))
            return
        except ValueError as exc:
            st.error("Backend вернул неожиданный ответ")
            st.code(str(exc))
            return

        if not isinstance(result, dict):
            st.error("Backend вернул неожиданный формат ответа")
            st.json(result)
            return

        st.session_state.vacancy = result
        st.session_state.vacancy_import_notice = {
            "message": "Вакансия импортирована из файла",
            "vacancy_id": result.get("vacancy_id") or result.get("id"),
            "title": result.get("title"),
            "company": result.get("company"),
            "source": result.get("source"),
            "description_length": result.get("description_length"),
        }
        st.session_state.vacancy_analysis = None
        _reset_downstream_vacancy_state()
        st.success("Вакансия импортирована из файла")
        st.toast("Вакансия импортирована из файла", icon="✅")
        st.rerun()


def _render_manual_vacancy_import(client: CareerCopilotApiClient, token: str | None) -> None:
    st.markdown("#### Ручной импорт")

    default_description = """Требования:
- Python
- FastAPI
- PostgreSQL

Будет плюсом:
- Redis
- Docker
"""

    use_demo_vacancy = st.checkbox(
        "Заполнить демо-вакансией",
        value=False,
        help="Используйте только для проверки demo-flow.",
    )

    with st.form("vacancy_import_form"):
        title_default = "Backend-разработчик" if use_demo_vacancy else ""
        company_default = "Тестовая компания" if use_demo_vacancy else ""
        location_default = "Удалённо" if use_demo_vacancy else ""
        description_default = default_description if use_demo_vacancy else ""

        title = st.text_input(
            "Название вакансии",
            value=title_default,
        )
        company = st.text_input(
            "Компания",
            value=company_default,
        )
        location = st.text_input(
            "Локация",
            value=location_default,
        )
        source_url = st.text_input(
            "Ссылка на вакансию",
            value="",
            help="Опционально. Для MVP можно оставить пустым.",
        )
        description_raw = st.text_area(
            "Текст вакансии",
            value=description_default,
            height=220,
            help="Вставьте требования и описание вакансии вручную.",
        )

        submitted = st.form_submit_button(
            "Импортировать вакансию",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if not description_raw.strip() and not source_url.strip():
            st.error("Нужно указать текст вакансии или ссылку на вакансию.")
            return

        payload = {
            "source": "manual",
            "source_url": source_url.strip() or None,
            "title": title.strip() or None,
            "company": company.strip() or None,
            "location": location.strip() or None,
            "description_raw": description_raw.strip() or None,
        }

        try:
            result = client.post_json("/vacancies/import",
                payload, token=token)
        except httpx.HTTPStatusError as exc:
            st.error(f"Backend вернул ошибку HTTP {exc.response.status_code}")
            st.code(exc.response.text)
            return
        except httpx.RequestError as exc:
            st.error("Не удалось подключиться к backend")
            st.code(str(exc))
            return
        except ValueError as exc:
            st.error("Backend вернул неожиданный ответ")
            st.code(str(exc))
            return

        if not isinstance(result, dict):
            st.error("Backend вернул неожиданный формат ответа")
            st.json(result)
            return

        st.session_state.vacancy = result
        st.session_state.vacancy_import_notice = None
        st.session_state.vacancy_analysis = None
        _reset_downstream_vacancy_state()
        st.success("Вакансия импортирована")


def render_vacancy_import_step(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.subheader("5. Импорт вакансии")

    notice = st.session_state.get("vacancy_import_notice")
    if isinstance(notice, dict):
        _render_vacancy_import_status(notice)

    achievements = st.session_state.achievements
    if not achievements:
        st.info("Сначала извлеките достижения на шаге 4.")
        return

    achievement_items = achievements.get("achievements") or []
    unconfirmed_achievements = [
        item for item in achievement_items if item.get("fact_status") != "confirmed"
    ]

    if unconfirmed_achievements:
        st.info(
            "Перед импортом вакансии подтвердите достижения на шаге 4. "
            "Это защищает pipeline от использования неподтверждённого опыта в документах."
        )
        return

    mode = st.radio(
        "Способ импорта вакансии",
        [
            "Ссылка HH",
            "Файл",
            "Ручной ввод",
        ],
        horizontal=True,
        key="vacancy_import_mode",
    )

    if mode == "Ссылка HH":
        _render_hh_vacancy_import(client, token)
    elif mode == "Файл":
        _render_file_vacancy_import(client, token)
    else:
        _render_manual_vacancy_import(client, token)

    if st.session_state.vacancy:
        vacancy = st.session_state.vacancy

        st.markdown("### Импортированная вакансия")
        st.markdown(f"**Название:** {vacancy.get('title') or '—'}")
        st.markdown(f"**Компания:** {vacancy.get('company') or '—'}")
        if vacancy.get("location"):
            st.markdown(f"**Локация:** {vacancy.get('location')}")
        st.caption(f"Источник: {_vacancy_source_label(vacancy.get('source'))}")

        with st.expander("Технические детали", expanded=False):
            st.json(
                {
                    "vacancy_id": vacancy.get("vacancy_id"),
                    "id": vacancy.get("id"),
                    "source": vacancy.get("source"),
                    "source_url": vacancy.get("source_url"),
                    "description_length": vacancy.get("description_length"),
                }
            )


def render_vacancy_analysis_step(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.subheader("6. Анализ вакансии")

    vacancy = st.session_state.vacancy
    if not vacancy:
        st.info("Сначала импортируйте вакансию на шаге 5.")
        return

    vacancy_id = vacancy.get("vacancy_id") or vacancy.get("id")
    if not vacancy_id:
        st.error("В результате импорта вакансии не найден vacancy_id.")
        st.json(vacancy)
        return

    with st.expander("Технические детали", expanded=False):
        st.caption(f"vacancy_id: {vacancy_id}")

    if st.button("Проанализировать вакансию", type="primary", use_container_width=True):
        try:
            result = client.post_json(f"/vacancies/{vacancy_id}/analyze",
                {}, token=token)
        except httpx.HTTPStatusError as exc:
            st.error(f"Backend вернул ошибку HTTP {exc.response.status_code}")
            st.code(exc.response.text)
            return
        except httpx.RequestError as exc:
            st.error("Не удалось подключиться к backend")
            st.code(str(exc))
            return
        except ValueError as exc:
            st.error("Backend вернул неожиданный ответ")
            st.code(str(exc))
            return

        if not isinstance(result, dict):
            st.error("Backend вернул неожиданный формат ответа")
            st.json(result)
            return

        st.session_state.vacancy_analysis = result
        st.session_state.generated_resume = None
        st.session_state.generated_cover_letter = None
        st.session_state.approved_resume = None
        st.session_state.approved_cover_letter = None
        st.session_state.application = None
        st.success("Вакансия проанализирована")

    if st.session_state.vacancy_analysis:
        analysis = st.session_state.vacancy_analysis

        st.markdown("### Результат анализа")

        col_left, col_right, col_center = st.columns(3)

        with col_left:
            st.metric("Совпадение", analysis.get("match_score"))

        with col_center:
            st.metric("Must-have", len(analysis.get("must_have") or []))

        with col_right:
            st.metric("Nice-to-have", len(analysis.get("nice_to_have") or []))

        with st.expander("Технические детали", expanded=False):
            st.caption(f"analysis_id: {analysis.get('analysis_id')}")
            st.caption(f"analysis_version: {analysis.get('analysis_version')}")

        must_have = analysis.get("must_have") or []
        nice_to_have = analysis.get("nice_to_have") or []
        strengths = analysis.get("strengths") or []
        gaps = analysis.get("gaps") or []

        col_must, col_nice = st.columns(2)

        with col_must:
            st.markdown("#### Must-have требования")
            if must_have:
                for item in must_have:
                    st.markdown(f"- {item.get('text', item)}")
            else:
                st.caption("Не найдено")

        with col_nice:
            st.markdown("#### Nice-to-have требования")
            if nice_to_have:
                for item in nice_to_have:
                    st.markdown(f"- {item.get('text', item)}")
            else:
                st.caption("Не найдено")

        col_strengths, col_gaps = st.columns(2)

        with col_strengths:
            st.markdown("#### Сильные совпадения")
            if strengths:
                for item in strengths:
                    keyword = item.get("keyword")
                    scope = item.get("scope")
                    weight = item.get("weight")
                    evidence = item.get("evidence")
                    st.success(f"{keyword}")
                    if evidence:
                        st.caption(f"Подтверждение: {evidence}")
            else:
                st.caption("Совпадений не найдено")

        with col_gaps:
            st.markdown("#### Gap-зоны")
            if gaps:
                for item in gaps:
                    keyword = item.get("keyword")
                    scope = item.get("scope")
                    weight = item.get("weight")
                    reason = item.get("reason")
                    st.warning(f"{keyword}")
                    if reason:
                        st.caption(f"Почему важно: {reason}")
            else:
                st.caption("Критичных gaps не найдено")

        keywords = analysis.get("keywords") or []
        if keywords:
            with st.expander("Ключевые слова", expanded=False):
                st.write(", ".join(keywords))

        with st.expander("Технический JSON результата", expanded=False):
            st.json(analysis)

    if vacancy_id:
        st.divider()
        _render_vacancy_intelligence_block(client, vacancy_id=str(vacancy_id), token=token)


def _render_vacancy_intelligence_block(
    client: CareerCopilotApiClient,
    *,
    vacancy_id: str,
    token: str | None = None,
) -> None:
    st.markdown("### Анализ вакансии")
    st.caption("Детерминированный разбор соответствия для операционных подсказок, а не вероятность найма.")

    try:
        fit = client.get_vacancy_fit(vacancy_id, token=token)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {400, 404}:
            st.info("Анализ вакансии доступен после анализа вакансии и извлечения профиля.")
        else:
            st.warning(f"Анализ вакансии недоступен: HTTP {exc.response.status_code}")
            st.code(exc.response.text)
        return
    except httpx.RequestError as exc:
        st.warning("Не удалось подключиться к backend для анализа вакансии.")
        st.code(str(exc))
        return
    except ValueError as exc:
        st.warning("Анализ вакансии вернул неожиданный ответ.")
        st.code(str(exc))
        return

    if not isinstance(fit, dict):
        st.warning("Анализ вакансии вернул неожиданный формат.")
        st.json(fit)
        return

    recommendation = str(fit.get("readiness_recommendation") or "—")
    gap_severity = str(fit.get("gap_severity") or "—")

    if recommendation == "Ready to apply":
        st.success("Готово к отклику")
    elif recommendation == "Apply with caution":
        st.warning("Отклик с осторожностью")
    else:
        st.error("Требует доработки")

    col_overall, col_skills, col_evidence, col_experience, col_leadership = st.columns(5)
    with col_overall:
        st.metric("Общий fit", fit.get("overall_fit_score", 0))
    with col_skills:
        st.metric("Навыки", fit.get("skills_fit", 0))
    with col_evidence:
        st.metric("Доказательства", fit.get("evidence_fit", 0))
    with col_experience:
        st.metric("Опыт", fit.get("experience_fit", 0))
    with col_leadership:
        st.metric("Лидерство", fit.get("leadership_fit", 0))

    st.caption(f"Серьёзность пробелов: {gap_severity}")
    if fit.get("analysis_version"):
        with st.expander("Технические детали", expanded=False):
            st.caption(f"analysis_version: {fit.get('analysis_version')}")

    coverage = fit.get("evidence_coverage") or {}
    _render_fit_summary(coverage)

    required = coverage.get("required") or []
    if required:
        st.markdown("#### Эта вакансия требует")
        for item in required:
            st.markdown(f"- {item}")

    def _render_coverage_group(label: str, items: list[dict[str, object]], kind: str) -> None:
        st.markdown(f"#### {label}")
        if not items:
            st.caption("—")
            return

        for item in items:
            requirement = str(item.get("requirement") or "Requirement")
            reason = _humanize_requirement_reason(item.get("reason"))
            supporting_evidence = item.get("supporting_evidence") or []

            with st.container(border=True):
                if kind == "strong":
                    st.success(requirement)
                elif kind == "medium":
                    st.warning(requirement)
                else:
                    st.info(requirement)
                st.caption(reason)

                if supporting_evidence:
                    with st.expander("Почему система так решила", expanded=False):
                        for evidence in supporting_evidence:
                            title = str(evidence.get("title") or "Подтверждённый опыт").strip()
                            fact_status = str(evidence.get("fact_status") or "—")
                            evidence_strength = str(evidence.get("evidence_strength") or "—")
                            st.markdown(f"**{title}**")
                            st.caption(
                                f"{_humanize_fact_status(fact_status)} · "
                                f"{_humanize_strength(evidence_strength)}"
                            )
                            star_preview = evidence.get("star_preview") or {}
                            if isinstance(star_preview, dict) and star_preview:
                                st.caption(
                                    "STAR-превью: "
                                    + ", ".join(
                                        f"{key}={value}"
                                        for key, value in star_preview.items()
                                        if value not in (None, "", [])
                                    )
                                )
                            snippet_text = str(evidence.get("snippet_text") or "").strip()
                            if snippet_text:
                                st.write(snippet_text)

    _render_coverage_group("Сильные доказательства", coverage.get("strong") or [], "strong")
    _render_coverage_group("Средние доказательства", coverage.get("medium") or [], "medium")
    _render_coverage_group("Без подтверждённых доказательств", coverage.get("missing") or [], "missing")


