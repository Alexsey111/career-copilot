# app/services/interview_answer_synthesis_service.py

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence


class InterviewAnswerSynthesisService:
    """Build deterministic interview answer drafts from STAR evidence."""

    def attach_suggested_answers(
        self,
        *,
        questions: list[dict[str, Any]],
        evidence_snippets: Sequence[Mapping[str, Any]],
        weak_areas: Sequence[Mapping[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        evidence_by_id = {
            str(item.get("id") or item.get("achievement_id") or "").strip(): dict(item)
            for item in evidence_snippets
            if str(item.get("id") or item.get("achievement_id") or "").strip()
        }
        weak_area_by_key = {
            str(item.get("competency_key") or "").strip(): dict(item)
            for item in (weak_areas or [])
            if str(item.get("competency_key") or "").strip()
        }

        enriched: list[dict[str, Any]] = []
        for question in questions:
            item = dict(question)
            item["suggested_answer"] = self.build_answer(
                question=item,
                evidence_by_id=evidence_by_id,
                weak_area=weak_area_by_key.get(
                    str(item.get("competency_key") or "").strip()
                ),
            )
            enriched.append(item)

        return enriched

    def build_answer(
        self,
        *,
        question: Mapping[str, Any],
        evidence_by_id: Mapping[str, Mapping[str, Any]],
        weak_area: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        evidence = self._select_question_evidence(question, evidence_by_id)
        category = str(question.get("category") or "").strip().lower()

        if category == "gap-risk":
            return self._build_gap_answer(question=question, weak_area=weak_area)

        star = self._resolve_star(evidence)
        skills = self._resolve_skills(evidence)
        competency = str(
            question.get("competency_name")
            or question.get("source_requirement")
            or question.get("competency_key")
            or ""
        ).strip()

        answer = {
            "format": "STAR_plus_tradeoffs",
            "situation": star.get("situation")
            or self._fallback_situation(evidence=evidence, competency=competency),
            "task": star.get("task")
            or self._fallback_task(evidence=evidence, competency=competency),
            "action": star.get("action")
            or self._fallback_action(evidence=evidence, competency=competency),
            "result": star.get("result")
            or self._fallback_result(evidence=evidence),
            "tech_stack": skills[:8],
            "tradeoffs": self._build_tradeoffs(
                question=question,
                evidence=evidence,
                skills=skills,
            ),
            "talking_points": self._build_talking_points(
                evidence=evidence,
                skills=skills,
                competency=competency,
            ),
            "source_evidence_id": str(evidence.get("id") or evidence.get("achievement_id") or "").strip()
            or None,
            "source_title": str(evidence.get("title") or "").strip() or None,
            "fact_status": str(evidence.get("fact_status") or "needs_review"),
            "requires_human_review": True,
        }
        answer["draft_text"] = self._render_draft_text(answer)
        return answer

    def _select_question_evidence(
        self,
        question: Mapping[str, Any],
        evidence_by_id: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any]:
        for evidence_id in question.get("recommended_evidence_ids") or []:
            item = evidence_by_id.get(str(evidence_id))
            if item:
                return dict(item)

        source_id = str(question.get("source_achievement_id") or "").strip()
        if source_id and source_id in evidence_by_id:
            return dict(evidence_by_id[source_id])

        return {}

    def _resolve_star(self, evidence: Mapping[str, Any]) -> dict[str, str]:
        star = dict(evidence.get("star_summary") or {})
        return {
            key: str(star.get(key) or "").strip()
            for key in ("situation", "task", "action", "result")
            if str(star.get(key) or "").strip()
        }

    def _resolve_skills(self, evidence: Mapping[str, Any]) -> list[str]:
        skills = [
            self._normalize_skill(str(skill))
            for skill in (evidence.get("skills") or [])
            if str(skill).strip()
        ]
        text = " ".join(
            [
                str(evidence.get("title") or ""),
                str(evidence.get("snippet_text") or ""),
                " ".join(skills),
            ]
        ).lower()
        inferred = [
            ("FastAPI", r"\bfastapi\b"),
            ("Python", r"\bpython\b"),
            ("PostgreSQL", r"\bpostgres(?:ql)?\b"),
            ("SQLAlchemy", r"\bsqlalchemy\b"),
            ("OpenAI", r"\bopenai\b"),
            ("AI Workflow", r"\bai workflow\b|\bworkflow\b|\borchestrat"),
            ("Docker", r"\bdocker\b"),
            ("Pytest", r"\bpytest\b|\btesting\b"),
        ]
        for label, pattern in inferred:
            if re.search(pattern, text, flags=re.IGNORECASE):
                skills.append(label)
        return self._dedupe(skills)

    def _build_gap_answer(
        self,
        *,
        question: Mapping[str, Any],
        weak_area: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        competency = str(
            question.get("competency_name")
            or question.get("competency_key")
            or "этой зоне"
        ).strip()
        message = str((weak_area or {}).get("message") or "").strip()
        limitation = message or f"нет сильного подтверждённого опыта по {competency}"
        answer = {
            "format": "honest_gap_response",
            "situation": f"По {competency} важно ответить честно и без overclaim.",
            "task": f"Показать понимание требования и план закрытия gap: {limitation}.",
            "action": (
                "Я бы прямо обозначил текущий уровень, связал его с ближайшим "
                "релевантным опытом и предложил конкретный план быстрого добора практики."
            ),
            "result": (
                "Такой ответ снижает риск неподтверждённых claims и показывает зрелый подход к обучению."
            ),
            "tech_stack": [],
            "tradeoffs": [
                "Не заявлять production experience без подтверждённых фактов",
                "Показывать adjacent experience и план онбординга",
            ],
            "talking_points": [
                f"Честно признать weak area: {competency}",
                "Связать с подтверждённым backend/automation опытом",
                "Назвать первые шаги: документация, spike, pairing, небольшой production task",
            ],
            "source_evidence_id": None,
            "source_title": None,
            "fact_status": "inferred_needs_review",
            "requires_human_review": True,
        }
        answer["draft_text"] = self._render_draft_text(answer)
        return answer

    def _fallback_situation(
        self,
        *,
        evidence: Mapping[str, Any],
        competency: str,
    ) -> str:
        title = str(evidence.get("title") or "").strip()
        if title:
            return f"В проекте {title} нужно было показать практический опыт по {competency or 'ключевой компетенции'}."
        return f"Нужно было привести проверяемый пример по {competency or 'ключевой компетенции'}."

    def _fallback_task(
        self,
        *,
        evidence: Mapping[str, Any],
        competency: str,
    ) -> str:
        skills = self._resolve_skills(evidence)
        if skills:
            return f"Сформулировать задачу через стек и вклад: {', '.join(skills[:4])}."
        return f"Объяснить задачу, ограничения и личный вклад по теме {competency or 'вопроса'}."

    def _fallback_action(
        self,
        *,
        evidence: Mapping[str, Any],
        competency: str,
    ) -> str:
        text = str(evidence.get("snippet_text") or "").strip()
        if text:
            return self._clean_sentence(text)
        if "fastapi" in competency.lower():
            return (
                "Спроектировал backend API, разделил ответственность между endpoint-ами, "
                "persistence layer и workflow logic."
            )
        return "Описал решение через concrete implementation steps и проверяемые evidence."

    def _fallback_result(self, *, evidence: Mapping[str, Any]) -> str:
        title = str(evidence.get("title") or "").strip()
        if title:
            return f"Получился подтверждаемый пример для интервью: {title}."
        return "Получился структурированный STAR-ответ, который нужно проверить перед интервью."

    def _build_tradeoffs(
        self,
        *,
        question: Mapping[str, Any],
        evidence: Mapping[str, Any],
        skills: list[str],
    ) -> list[str]:
        text = " ".join(
            [
                str(question.get("prompt") or ""),
                str(evidence.get("title") or ""),
                str(evidence.get("snippet_text") or ""),
                " ".join(skills),
            ]
        ).lower()
        tradeoffs: list[str] = []
        if "fastapi" in text or "backend" in text:
            tradeoffs.append("Разделить API layer, business workflow и persistence boundaries")
        if "postgres" in text or "sqlalchemy" in text:
            tradeoffs.append("Балансировать простоту модели данных и возможность расширения")
        if "workflow" in text or "openai" in text or "llm" in text:
            tradeoffs.append("Сохранять deterministic review flow вокруг AI-generated output")
        if "testing" in text or "pytest" in text:
            tradeoffs.append("Покрывать критичные ветки тестами вместо проверки только happy path")
        return tradeoffs or ["Держать ответ grounded in confirmed evidence без лишних claims"]

    def _build_talking_points(
        self,
        *,
        evidence: Mapping[str, Any],
        skills: list[str],
        competency: str,
    ) -> list[str]:
        points: list[str] = []
        if competency:
            points.append(f"Начать с связи ответа с компетенцией: {competency}")
        if evidence.get("title"):
            points.append(f"Назвать проект/факт: {evidence.get('title')}")
        if skills:
            points.append(f"Упомянуть стек: {', '.join(skills[:5])}")
        points.append("Закрыть ответ результатом и тем, что было проверено evidence")
        return points

    def _render_draft_text(self, answer: Mapping[str, Any]) -> str:
        lines = [
            f"Situation: {answer.get('situation')}",
            f"Task: {answer.get('task')}",
            f"Action: {answer.get('action')}",
            f"Result: {answer.get('result')}",
        ]
        tech_stack = answer.get("tech_stack") or []
        if tech_stack:
            lines.append(f"Tech stack: {', '.join(str(item) for item in tech_stack)}")
        tradeoffs = answer.get("tradeoffs") or []
        if tradeoffs:
            lines.append(
                "Tradeoffs: " + "; ".join(str(item) for item in tradeoffs[:3])
            )
        return "\n".join(line for line in lines if line and not line.endswith(": None"))

    def _normalize_skill(self, value: str) -> str:
        cleaned = re.sub(r"\s+", " ", value).strip(" .;-–—•")
        known = {
            "llm": "LLM",
            "ai": "AI",
            "openai": "OpenAI",
            "chatgpt": "ChatGPT",
            "python": "Python",
            "fastapi": "FastAPI",
            "sqlalchemy": "SQLAlchemy",
            "postgresql": "PostgreSQL",
            "ai workflow": "AI Workflow",
        }
        return known.get(cleaned.lower(), cleaned)

    def _clean_sentence(self, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip(" .;-–—•")

    def _dedupe(self, values: Sequence[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            cleaned = self._clean_sentence(str(value))
            key = cleaned.lower()
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(cleaned)
        return result
