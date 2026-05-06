# app\services\interview_preparation_service.py

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.candidate_profile_repository import CandidateProfileRepository
from app.repositories.interview_session_repository import InterviewSessionRepository
from app.repositories.vacancy_analysis_repository import VacancyAnalysisRepository
from app.repositories.vacancy_repository import VacancyRepository


class InterviewPreparationService:
    def __init__(
        self,
        interview_session_repository: InterviewSessionRepository | None = None,
        vacancy_repository: VacancyRepository | None = None,
        vacancy_analysis_repository: VacancyAnalysisRepository | None = None,
        candidate_profile_repository: CandidateProfileRepository | None = None,
        ai_orchestrator: Any | None = None,
    ) -> None:
        self.interview_session_repository = (
            interview_session_repository or InterviewSessionRepository()
        )
        self.vacancy_repository = vacancy_repository or VacancyRepository()
        self.vacancy_analysis_repository = (
            vacancy_analysis_repository or VacancyAnalysisRepository()
        )
        self.candidate_profile_repository = (
            candidate_profile_repository or CandidateProfileRepository()
        )
        self.ai_orchestrator = ai_orchestrator

    async def create_session(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        vacancy_id: UUID,
        session_type: str,
    ):
        vacancy = await self.vacancy_repository.get_by_id(
            session,
            vacancy_id,
            user_id=user_id,
        )
        if vacancy is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="vacancy not found",
            )

        analysis = await self.vacancy_analysis_repository.get_latest_for_vacancy(
            session,
            vacancy_id,
            user_id=user_id,
        )
        if analysis is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="vacancy analysis not found; run vacancy analysis first",
            )

        profile = await self.candidate_profile_repository.get_with_related_by_user_id(
            session,
            user_id,
        )
        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="candidate profile not found; run profile extraction first",
            )

        question_set = self._build_question_set(
            vacancy_title=vacancy.title,
            company=vacancy.company,
            must_have=analysis.must_have_json,
            nice_to_have=analysis.nice_to_have_json,
            strengths=analysis.strengths_json,
            gaps=analysis.gaps_json,
            achievements=[
                {
                    "title": item.title,
                    "fact_status": item.fact_status,
                }
                for item in profile.achievements
            ],
        )

        interview_session = await self.interview_session_repository.create(
            session,
            user_id=user_id,
            vacancy_id=vacancy.id,
            session_type=session_type.strip().lower() or "vacancy",
            status="draft",
            question_set_json=question_set,
            answers_json=[],
            feedback_json={},
            score_json={},
        )

        await session.commit()
        await session.refresh(interview_session)
        return interview_session

    async def get_session(
        self,
        session: AsyncSession,
        *,
        session_id: UUID,
        user_id: UUID,
    ):
        interview_session = await self.interview_session_repository.get_by_id(
            session,
            session_id,
            user_id=user_id,
        )
        if interview_session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="interview session not found",
            )

        return interview_session

    async def list_session_dashboard_items(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
    ) -> list[dict]:
        return await self.interview_session_repository.list_dashboard_by_user_id(
            session,
            user_id,
        )

    async def save_answers(
        self,
        session: AsyncSession,
        *,
        session_id: UUID,
        user_id: UUID,
        answers: list[dict],
    ):
        interview_session = await self.get_session(
            session,
            session_id=session_id,
            user_id=user_id,
        )

        normalized_answers = self._validate_and_normalize_answers(
            question_set=interview_session.question_set_json,
            answers=answers,
        )
        feedback_json = self._build_feedback(
            question_set=interview_session.question_set_json,
            answers=normalized_answers,
        )
        score_json = self._build_score(
            feedback_json,
            total_question_count=len(interview_session.question_set_json),
        )

        interview_session = await self.interview_session_repository.save_answers(
            session,
            interview_session,
            answers_json=normalized_answers,
            feedback_json=feedback_json,
            score_json=score_json,
            status="answered",
        )

        await session.commit()
        await session.refresh(interview_session)
        return interview_session

    def _validate_and_normalize_answers(
        self,
        *,
        question_set: list[dict],
        answers: list[dict],
    ) -> list[dict]:
        max_index = len(question_set) - 1
        seen_indexes: set[int] = set()
        normalized: list[dict] = []

        for item in answers:
            question_index = int(item["question_index"])

            if question_index < 0 or question_index > max_index:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"question_index out of range: {question_index}",
                )

            if question_index in seen_indexes:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"duplicate answer for question_index: {question_index}",
                )

            seen_indexes.add(question_index)
            question = question_set[question_index]
            answer_text = str(item.get("answer_text", "")).strip()

            normalized.append(
                {
                    "question_index": question_index,
                    "question_type": question.get("type"),
                    "answer_format": question.get("answer_format"),
                    "answer_text": answer_text,
                }
            )

        return normalized

    def _build_feedback(
        self,
        *,
        question_set: list[dict],
        answers: list[dict],
    ) -> dict:
        items: list[dict] = []

        for answer in answers:
            question_index = answer["question_index"]
            question = question_set[question_index]
            answer_text = answer["answer_text"]
            answer_lower = answer_text.lower()

            warnings: list[str] = []
            suggestions: list[str] = []

            if not answer_text:
                warnings.append("empty_answer")
                suggestions.append(
                    "Добавьте конкретный ответ перед использованием в подготовке к интервью."
                )
            else:
                if question.get("answer_format") in {"STAR", "STAR_or_example"}:
                    star_markers = self._count_star_markers(answer_lower)
                    if star_markers < 2:
                        warnings.append("weak_star_structure")
                        suggestions.append(
                            "Усильте ответ по структуре STAR: ситуация, задача, действия, результат."
                        )

                if question.get("type") == "gap_preparation":
                    risky_phrases = self._find_overclaim_phrases(answer_lower)
                    if risky_phrases:
                        warnings.append("possible_gap_overclaim")
                        suggestions.append(
                            "Это ответ по gap-зоне. Не представляйте слабый или отсутствующий опыт "
                            "как подтверждённую экспертизу."
                        )

                if self._contains_unverified_metric(answer_text):
                    warnings.append("metric_needs_confirmation")
                    suggestions.append(
                        "Подтвердите метрику перед тем, как использовать её как сильное утверждение."
                    )

            items.append(
                {
                    "question_index": question_index,
                    "question_type": question.get("type"),
                    "warnings": warnings,
                    "suggestions": suggestions,
                    "answer_length": len(answer_text),
                }
            )

        return {
            "feedback_version": "deterministic_v1",
            "items": items,
        }

    def _build_score(
        self,
        feedback_json: dict,
        *,
        total_question_count: int | None = None,
    ) -> dict:
        items = feedback_json.get("items", [])
        answered_count = sum(1 for item in items if item.get("answer_length", 0) > 0)
        warning_count = sum(len(item.get("warnings", [])) for item in items)

        question_count = (
            total_question_count if total_question_count is not None else len(items)
        )
        unanswered_count = max(0, question_count - answered_count)

        if question_count == 0:
            readiness_score = None
        else:
            raw_score = 100
            raw_score -= warning_count * 15
            raw_score -= unanswered_count * 8
            readiness_score = max(0, min(100, raw_score))

        return {
            "score_version": "deterministic_v2",
            "question_count": question_count,
            "answered_count": answered_count,
            "unanswered_count": unanswered_count,
            "warning_count": warning_count,
            "readiness_score": readiness_score,
        }

    def _count_star_markers(self, answer_lower: str) -> int:
        markers = [
            "situation",
            "task",
            "action",
            "result",
            "ситуация",
            "задача",
            "действие",
            "действия",
            "результат",
        ]
        return sum(1 for marker in markers if marker in answer_lower)

    def _find_overclaim_phrases(self, answer_lower: str) -> list[str]:
        risky_phrases = [
            "expert",
            "senior",
            "production experience",
            "commercial experience",
            "эксперт",
            "сеньор",
            "senior-разработчик",
            "уверенный опыт",
            "коммерческий опыт",
            "глубокий опыт",
        ]
        return [phrase for phrase in risky_phrases if phrase in answer_lower]

    def _contains_unverified_metric(self, answer_text: str) -> bool:
        if "%" in answer_text:
            return True

        return False

    def _word_count(self, text: str) -> int:
        return len(text.split())

    def _is_safe_enhancement(self, original: str, enhanced: str) -> bool:
        orig_words = self._word_count(original)
        enh_words = self._word_count(enhanced)

        # Если улучшенный ответ более чем в 5 раз длиннее - подозрительно
        if enh_words > orig_words * 5:
            return False

        return True

    def compute_progress(self, attempts: list) -> dict:
        """
        Вычисляет прогресс по попыткам ответа.
        
        Args:
            attempts: список попыток (InterviewAnswerAttempt)
        
        Returns:
            dict с first_score, last_score, improvement
        """
        if not attempts:
            return {
                "first_score": None,
                "last_score": None,
                "improvement": None,
            }

        scores = [a.score for a in attempts if a.score is not None]
        
        if not scores:
            return {
                "first_score": None,
                "last_score": None,
                "improvement": None,
            }

        return {
            "first_score": scores[0],
            "last_score": scores[-1],
            "improvement": scores[-1] - scores[0],
        }

    @staticmethod
    def build_attempt_diff(prev: str, current: str) -> dict:
        """
        Сравнивает два ответа и показывает добавленные/удалённые ключевые слова.
        
        Args:
            prev: текст предыдущего ответа
            current: текста текущего ответа
        
        Returns:
            dict с added_keywords и removed_keywords
        """
        prev_words = set(prev.lower().split())
        curr_words = set(current.lower().split())
        
        added = list(curr_words - prev_words)
        removed = list(prev_words - curr_words)
        
        return {
            "added_keywords": added[:10],
            "removed_keywords": removed[:10],
        }

    @staticmethod
    def build_attempt_insight(prev_attempt, current_attempt) -> dict:
        """
        Формирует insight о прогрессе между двумя попытками.
        
        Args:
            prev_attempt: предыдущая попытка (InterviewAnswerAttempt)
            current_attempt: текущая попытка (InterviewAnswerAttempt)
        
        Returns:
            dict с improved, score_delta, diff
        """
        diff = InterviewPreparationService.build_attempt_diff(
            prev_attempt.answer_text or "",
            current_attempt.answer_text or ""
        )

        improved = (current_attempt.score or 0) > (prev_attempt.score or 0)
        score_delta = (current_attempt.score or 0) - (prev_attempt.score or 0)
        
        return {
            "improved": improved,
            "score_delta": score_delta,
            "diff": diff,
        }

    def _evaluate_answer_basic(
        self,
        *,
        question: str,
        answer: str,
    ) -> dict:
        """
        Базовая детерминированная оценка ответа (без AI).
        
        Критерии:
        1. Длина (proxy на глубину)
        2. Наличие конкретики (цифры)
        3. Наличие глаголов действия
        4. Структура STAR
        """
        score = 0
        feedback = []

        # 1. Длина (proxy на глубину)
        if len(answer.split()) > 20:
            score += 1
        else:
            feedback.append("Answer is too short")

        # 2. Наличие конкретики (очень грубо)
        if any(word.isdigit() for word in answer.split()):
            score += 1
        else:
            feedback.append("No measurable results mentioned")

        # 3. Наличие глаголов действия
        action_words = ["built", "implemented", "designed", "led"]
        answer_lower = answer.lower()
        if any(w in answer_lower for w in action_words):
            score += 1
        else:
            feedback.append("Lacks strong action verbs")

        # 4. Структура (очень MVP)
        if "situation" in answer_lower or "result" in answer_lower:
            score += 1
        else:
            feedback.append("STAR structure not clear")

        return {
            "score": score / 4,
            "feedback": feedback,
        }

    async def coach_answer(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        question: str,
        answer: str,
        evaluation: dict,
        language: str = "ru",
    ) -> dict:
        """
        AI-коуч: улучшает ответ с учётом детерминированной оценки.
        
        Использует safety guard для защиты от выдумок.
        """
        if not self.ai_orchestrator:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="AI orchestrator not configured",
            )

        from app.ai.orchestrator import AIOrchestrator
        from app.ai.registry.prompts import PromptTemplate

        evaluation_text = f"Score: {evaluation.get('score', 0)}/1. Feedback: {', '.join(evaluation.get('feedback', []))}"

        result = await self.ai_orchestrator.execute(
            session=session,
            user_id=user_id,
            prompt_template=PromptTemplate.INTERVIEW_COACH_V1,
            prompt_vars={
                "question": question,
                "answer": answer,
                "evaluation": evaluation_text,
            },
            workflow_name="interview_coach",
            target_type="interview_answer",
            language=language,
        )

        improved = result["result"]["improved_answer"]

        # reuse guard!
        if not self._is_safe_enhancement(answer, improved):
            return {
                "improved_answer": answer,
                "explanation": "AI suggestion rejected (safety guard)",
            }

        return result["result"]

    async def improve_answer_with_ai(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        question: str,
        answer: str,
        evaluation: dict,
        language: str = "ru",
    ) -> dict:
        """
        AI-улучшение ответа на вопрос собеседования.
        
        Использует детерминированную оценку как контекст для AI.
        """
        if not self.ai_orchestrator:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="AI orchestrator not configured",
            )

        from app.ai.orchestrator import AIOrchestrator
        from app.ai.registry.prompts import PromptTemplate

        evaluation_text = f"Score: {evaluation.get('score', 0)}/1. Feedback: {', '.join(evaluation.get('feedback', []))}"

        result = await self.ai_orchestrator.execute(
            session=session,
            user_id=user_id,
            prompt_template=PromptTemplate.INTERVIEW_COACH_V1,
            prompt_vars={
                "question": question,
                "answer": answer,
                "evaluation": evaluation_text,
            },
            workflow_name="interview_coach",
            target_type="interview_answer",
            language=language,
        )

        return result["result"]

    async def generate_coaching_hint(
        self,
        *,
        prev_attempt,
        current_attempt,
        diff: dict,
        orchestrator: Any,
        session: AsyncSession,
        user_id: UUID,
    ):
        """
        Генерирует coaching-фидбек на основе сравнения двух попыток ответа.
        
        Args:
            prev_attempt: предыдущая попытка (InterviewAnswerAttempt)
            current_attempt: текущая попытка (InterviewAnswerAttempt)
            diff: результат build_attempt_diff (added_keywords, removed_keywords)
            orchestrator: AIOrchestrator
            session: AsyncSession
            user_id: UUID пользователя
        
        Returns:
            dict с improvement, gap, next_step
        """
        from app.ai.registry.prompts import PromptTemplate

        score_delta = (current_attempt.score or 0) - (prev_attempt.score or 0)

        result = await orchestrator.execute(
            session=session,
            user_id=user_id,
            prompt_template=PromptTemplate.INTERVIEW_COACHING_V1,
            prompt_vars={
                "previous_answer": prev_attempt.answer_text or "",
                "current_answer": current_attempt.answer_text or "",
                "score_delta": str(score_delta),
                "added_keywords": diff["added_keywords"],
                "removed_keywords": diff["removed_keywords"],
            },
            workflow_name="interview_coaching",
            target_type="interview_session",
            target_id=str(current_attempt.session_id),
        )

        return result["result"]

    def _build_question_set(
        self,
        *,
        vacancy_title: str,
        company: str | None,
        must_have: list[dict],
        nice_to_have: list[dict],
        strengths: list[dict],
        gaps: list[dict],
        achievements: list[dict],
    ) -> list[dict]:
        company_part = company or "компании"
        questions: list[dict] = []

        questions.append(
            {
                "type": "role_overview",
                "source": "vacancy",
                "prompt": (
                    f"Кратко объясните, почему вам интересна позиция {vacancy_title} "
                    f"в {company_part} и чем ваш опыт может быть релевантен этой роли."
                ),
                "answer_format": "short_structured",
                "rubric": [
                    "Показывает понимание роли",
                    "Связывает мотивацию с релевантным опытом",
                    "Не содержит неподтверждённых утверждений",
                ],
            }
        )

        for item in must_have[:6]:
            requirement_text = item.get("text")
            if not requirement_text:
                continue

            questions.append(
                {
                    "type": "must_have_requirement",
                    "source": "vacancy_analysis.must_have",
                    "requirement_text": requirement_text,
                    "prompt": (
                        f"Опишите ваш практический опыт по этому требованию: "
                        f"{requirement_text}."
                    ),
                    "answer_format": "STAR_or_example",
                    "rubric": [
                        "Есть конкретный пример",
                        "Личный вклад отделён от командного контекста",
                        "Инструменты, масштаб и результат указаны только там, где это фактологично",
                    ],
                }
            )

        for item in gaps[:5]:
            keyword = item.get("keyword")
            scope = item.get("scope")
            requirement_text = item.get("requirement_text") or keyword
            if not keyword:
                continue

            questions.append(
                {
                    "type": "gap_preparation",
                    "source": "vacancy_analysis.gaps",
                    "keyword": keyword,
                    "scope": scope,
                    "requirement_text": requirement_text,
                    "prompt": (
                        f"В вакансии ожидается {requirement_text}, но текущий профиль пока "
                        f"не даёт сильного подтверждения. Как честно ответить на вопрос "
                        f"о вашем уровне в {keyword}?"
                    ),
                    "answer_format": "honest_gap_response",
                    "rubric": [
                        "Не выдумывает опыт",
                        "Чётко называет реальный уровень знакомства с темой",
                        "Показывает реалистичный план дообучения или переноса смежного опыта",
                    ],
                }
            )

        for item in strengths[:5]:
            keyword = item.get("keyword")
            scope = item.get("scope")
            requirement_text = item.get("requirement_text") or keyword
            if not keyword:
                continue

            questions.append(
                {
                    "type": "strength_deep_dive",
                    "source": "vacancy_analysis.strengths",
                    "keyword": keyword,
                    "scope": scope,
                    "requirement_text": requirement_text,
                    "prompt": (
                        f"Подготовьте более глубокий пример, который подтверждает ваш опыт "
                        f"с {keyword} в контексте требования: {requirement_text}."
                    ),
                    "answer_format": "STAR",
                    "rubric": [
                        "Ситуация и задача понятны",
                        "Действия описаны конкретно",
                        "Результат фактологичен и не завышен",
                    ],
                }
            )

        for item in achievements[:3]:
            title = item.get("title")
            fact_status = item.get("fact_status")
            if not title:
                continue

            questions.append(
                {
                    "type": "achievement_star_story",
                    "source": "candidate_achievements",
                    "achievement_title": title,
                    "fact_status": fact_status,
                    "prompt": (
                        f"Превратите это достижение в STAR-историю для собеседования: {title}."
                    ),
                    "answer_format": "STAR",
                    "rubric": [
                        "Факт достижения подтверждён перед сильным использованием",
                        "Личный вклад кандидата понятен",
                        "Не добавлены неподтверждённые метрики",
                    ],
                }
            )

        return questions[:15]

    def _build_questions(
        self,
        *,
        strengths: list[str],
        gaps: list[str],
        achievements: list[str] | None = None,
    ) -> list[dict]:
        """
        Строит список вопросов для собеседования.
        
        Ключевая идея: gap → прямой вопрос
        Это то, что реально происходит на интервью.
        """
        achievements = achievements or []
        questions = []

        # Strength-based
        for skill in strengths[:3]:
            expected = self._build_expected_answer(
                skill=skill,
                achievements=achievements,
            )
            questions.append({
                "type": "strength",
                "skill": skill,
                "question": f"Can you describe your experience with {skill}?",
                "expected_answer": expected,
            })

        # Gap-based (самое ценное)
        for gap in gaps[:3]:
            expected = self._build_expected_answer(
                skill=gap,
                achievements=achievements,
            )
            questions.append({
                "type": "gap",
                "skill": gap,
                "question": f"You have less experience with {gap}. How are you addressing this?",
                "expected_answer": expected,
            })

        return questions

    def _build_expected_answer(
        self,
        *,
        skill: str,
        achievements: list[str],
    ) -> str:
        relevant = [
            a for a in achievements if skill.lower() in a.lower()
        ]

        if not relevant:
            return "Explain learning efforts and practical steps taken."

        return "Use STAR format: " + "; ".join(relevant[:2])
