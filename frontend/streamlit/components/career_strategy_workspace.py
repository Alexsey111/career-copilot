from __future__ import annotations

from typing import Any

import httpx
import streamlit as st

from api_client import CareerCopilotApiClient


CAREER_STRATEGY_TEXT_REPLACEMENTS = {
    "Strong confirmed evidence with a reusable track record.": "Подтверждённое сильное доказательство с хорошей историей повторного использования.",
    "Evidence strength is weak. Review the wording, metrics, or supporting context before reuse.": "Сила доказательства низкая. Перед повторным использованием проверьте формулировку, метрики и контекст.",
    "No measurable metrics were detected. Add concrete numbers or outcome signals if they exist.": "Не обнаружены измеримые метрики. Если они есть, добавьте конкретные числа или сигналы результата.",
    "STAR coverage is incomplete. Fill in the missing Situation, Task, Action, or Result fields.": "Покрытие STAR неполное. Заполните отсутствующие поля Situation, Task, Action или Result.",
    "This evidence has not been used yet. Consider it for upcoming resume or interview drafts.": "Это доказательство пока не использовалось. Рассмотрите его для будущих черновиков резюме или интервью.",
    "This evidence is reused often. Consider rotating in alternative evidence to avoid repetition.": "Это доказательство используется слишком часто. Подумайте о чередовании с альтернативными доказательствами, чтобы избежать повторов.",
    "This fact is not confirmed yet. Keep it out of strong evidence paths until reviewed.": "Этот факт ещё не подтверждён. Не включайте его в сильные evidence-пути до проверки.",
    "Strengthen system design evidence": "Усилить доказательства по system design",
    "System design is recurring. Capture an example with tradeoffs, scale, and rationale.": "System design повторяется. Зафиксируйте пример с компромиссами, масштабом и обоснованием.",
    "Create STAR examples for Kubernetes": "Создать STAR-примеры для Kubernetes",
    "Kubernetes appears as a recurring gap. Build one precise STAR story that shows actual delivery or operations work.": "Kubernetes повторяется как пробел. Подготовьте один точный STAR-случай, показывающий реальную работу по delivery или operations.",
    "Strengthen quantified impact metrics": "Усилить количественные метрики эффекта",
    "Evidence around leadership looks weak or repeated. Add numbers, outcomes, or scale indicators to improve reuse.": "Доказательства по leadership выглядят слабо или повторяются. Добавьте цифры, результаты или показатели масштаба, чтобы усилить повторное использование.",
    "Reuse unused evidence": "Повторно использовать неиспользованные доказательства",
    "You have unused evidence that could support future resume or interview drafts.": "У вас есть неиспользованные доказательства, которые могут помочь в будущих черновиках резюме или интервью.",
    "Add quantified impact metrics": "Добавить количественные метрики эффекта",
    "Some evidence still lacks metrics. Quantified outcomes usually make fit and reuse stronger.": "В части доказательств всё ещё не хватает метрик. Количественные результаты обычно делают fit и повторное использование сильнее.",
    "Focus on the common rejection stage": "Сфокусироваться на общем этапе отказа",
    "Most rejections are happening around interview. Review the matching evidence and gaps for that stage.": "Большинство отказов происходит на этапе интервью. Проверьте соответствующие доказательства и пробелы именно для этого этапа.",
}


def _format_count(value: Any) -> str:
    try:
        return str(int(value or 0))
    except (TypeError, ValueError):
        return "0"


def _translate_career_strategy_text(value: str | None) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return CAREER_STRATEGY_TEXT_REPLACEMENTS.get(text, text)


def _render_application_patterns(patterns: dict[str, Any] | None) -> None:
    patterns = patterns or {}
    st.markdown("### Анализ паттернов откликов")
    col_sent, col_interviews, col_offers, col_conv = st.columns(4)

    with col_sent:
        st.metric("Отправлено откликов", patterns.get("applications_sent", 0))
    with col_interviews:
        st.metric("Дошло до интервью", patterns.get("interviews_reached", 0))
    with col_offers:
        st.metric("Офферы", patterns.get("offers_count", 0))
    with col_conv:
        st.metric(
            "Конверсия в интервью",
            f"{round(float(patterns.get('conversion_to_interview') or 0) * 100)}%",
        )

    st.caption(
        "Самый частый этап отказа: "
        f"{patterns.get('most_common_rejection_stage') or '—'} "
        f"({patterns.get('most_common_rejection_stage_count', 0)})"
    )
    st.caption(
        "Конверсия в оффер: "
        f"{round(float(patterns.get('conversion_to_offer') or 0) * 100)}%"
    )


def _render_repeated_gaps(repeated_gaps: list[dict[str, Any]]) -> None:
    st.markdown("### Слабые места")
    if not repeated_gaps:
        st.success("Слабые места пока не обнаружены.")
        return

    rows = []
    for item in repeated_gaps[:10]:
        rows.append(
            {
                "Пробел": item.get("keyword") or "—",
                "Количество": item.get("count", 0),
                "Серьёзность": item.get("severity") or "—",
                "Примеры": ", ".join(item.get("example_vacancy_titles") or []) or "—",
            }
        )
    st.dataframe(rows, width="stretch", hide_index=True)


def _render_evidence_coverage_trends(trends: dict[str, Any] | None) -> None:
    trends = trends or {}
    st.markdown("### Тренды покрытия доказательств")

    most_reusable = trends.get("most_reusable_evidence") or []
    unused = trends.get("unused_evidence") or []
    weak_clusters = trends.get("weak_evidence_clusters") or []

    col_reusable, col_unused, col_clusters = st.columns(3)

    with col_reusable:
        st.metric("Наиболее переиспользуемые", len(most_reusable))
    with col_unused:
        st.metric("Неиспользованные", len(unused))
    with col_clusters:
        st.metric("Слабые кластеры", len(weak_clusters))

    if most_reusable:
        st.markdown("#### Наиболее переиспользуемые доказательства")
        for item in most_reusable[:5]:
            st.markdown(f"- **{item.get('title') or 'Evidence'}**")
            st.caption(
                f"использований={_format_count(item.get('usage_count'))} · "
                f"сила={item.get('evidence_strength') or '—'} · "
                f"статус факта={item.get('fact_status') or '—'}"
            )
            if item.get("reason"):
                st.caption(_translate_career_strategy_text(str(item.get("reason"))))

    if unused:
        st.markdown("#### Неиспользованные доказательства")
        for item in unused[:5]:
            st.markdown(f"- {item.get('title') or 'Evidence'}")

    if weak_clusters:
        st.markdown("#### Слабые кластеры доказательств")
        for item in weak_clusters[:5]:
            examples = ", ".join(item.get("example_evidence_titles") or []) or "—"
            st.markdown(
                f"- {item.get('skill') or '—'}"
                f" ({item.get('count', 0)})"
            )
            st.caption(f"Примеры: {examples}")


def _render_recommendations(recommendations: list[dict[str, Any]]) -> None:
    st.markdown("### Стратегические рекомендации")
    if not recommendations:
        st.success("Стратегических рекомендаций пока нет.")
        return

    for item in recommendations:
        priority = str(item.get("priority") or "low").lower()
        title = _translate_career_strategy_text(str(item.get("title") or "Recommendation"))
        message = _translate_career_strategy_text(str(item.get("message") or ""))
        if priority == "high":
            st.error(title)
        elif priority == "medium":
            st.warning(title)
        else:
            st.info(title)
        if message:
            st.write(message)


def render_career_strategy_workspace_tab(
    client: CareerCopilotApiClient,
    *,
    token: str | None = None,
) -> None:
    st.header("Стратегия карьеры")
    st.caption(
        "Детерминированные операционные рекомендации: повторяющиеся пробелы, "
        "тренды покрытия доказательств, паттерны откликов и конкретные следующие шаги."
    )

    if not token:
        st.warning("Войдите, чтобы открыть стратегию карьеры.")
        return

    try:
        summary = client.get_career_insights(token=token)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            st.info("Карьерные инсайты доступны после появления профиля, вакансии, доказательств и отклика.")
        else:
            st.error(f"Backend returned HTTP {exc.response.status_code}")
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

    if not isinstance(summary, dict):
        st.error("Backend вернул неожиданный payload карьерных инсайтов")
        st.json(summary)
        return

    col_gaps, col_evidence, col_apps = st.columns(3)
    with col_gaps:
        st.metric("Слабые места", len(summary.get("repeated_gaps") or []))
    with col_evidence:
        coverage = summary.get("evidence_coverage_trends") or {}
        st.metric("Переиспользуемые доказательства", len(coverage.get("most_reusable_evidence") or []))
    with col_apps:
        patterns = summary.get("application_patterns") or {}
        st.metric("Отправлено откликов", patterns.get("applications_sent", 0))

    _render_repeated_gaps(summary.get("repeated_gaps") or [])
    st.divider()
    _render_evidence_coverage_trends(summary.get("evidence_coverage_trends") or {})
    st.divider()
    _render_application_patterns(summary.get("application_patterns") or {})
    st.divider()
    _render_recommendations(summary.get("strategic_recommendations") or [])

    sample = summary.get("vacancy_intelligence_sample") or []
    if sample:
        with st.expander("Пример анализа вакансии", expanded=False):
            st.json(sample)
