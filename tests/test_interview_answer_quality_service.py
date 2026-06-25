from app.services.interview_answer_quality_service import InterviewAnswerQualityService


def test_interview_answer_quality_scores_grounded_answer() -> None:
    service = InterviewAnswerQualityService()

    report = service.evaluate(
        {
            "situation": "Нужно было подготовить макеты для печати.",
            "task": "Адаптировать материалы под требования типографии.",
            "action": "Подготовила макеты в Adobe Photoshop.",
            "result": "Материалы были переданы в печать без доработок, срок сократился на 30%.",
            "source_evidence_id": "ev-1",
            "source_title": "Сократила сроки подготовки макетов на 30%",
            "tech_stack": ["Adobe Photoshop"],
            "grounding_status": "grounded",
            "requires_human_review": True,
        }
    )

    assert report.score >= 70
    assert report.grade in {"good", "excellent"}
    assert report.metrics["evidence_usage"] == 25
    assert report.strengths


def test_interview_answer_quality_penalizes_missing_evidence() -> None:
    service = InterviewAnswerQualityService()

    report = service.evaluate(
        {
            "situation": "Пока нет достаточно подтверждённого примера для безопасного STAR-ответа.",
            "task": "Подготовить реальный пример по теме Adobe Photoshop.",
            "action": "Не добавлять неподтверждённые действия или личный вклад.",
            "result": "Добавить подтверждённый результат, если он реально известен.",
            "grounding_status": "insufficient_evidence",
            "requires_human_review": True,
        }
    )

    assert report.score < 70
    assert any(issue.code == "missing_evidence" for issue in report.issues)
    assert any(issue.code == "incomplete_star" for issue in report.issues)


def test_interview_answer_quality_caps_placeholder_star_completeness() -> None:
    service = InterviewAnswerQualityService()

    report = service.evaluate(
        {
            "situation": "Есть релевантный факт: Сократила сроки подготовки макетов на 30%.",
            "task": "Дособрать задачу, личный вклад и результат по теме Adobe Photoshop.",
            "action": "Уточнить, что именно вы сделали лично.",
            "result": "Добавить проверяемый результат или метрику, если она реально известна.",
            "source_evidence_id": "ev-1",
            "source_title": "Сократила сроки подготовки макетов на 30%",
            "tech_stack": ["Adobe Photoshop"],
            "grounding_status": "partial_evidence",
            "requires_human_review": True,
        }
    )

    assert report.metrics["star_completeness"] <= 15
    assert report.score < 85
    assert report.grade != "excellent"
    assert any(issue.code == "incomplete_star" for issue in report.issues)


def test_interview_answer_quality_detects_overclaim_risk() -> None:
    service = InterviewAnswerQualityService()

    report = service.evaluate(
        {
            "situation": "Был проект.",
            "task": "Нужно было сделать работу.",
            "action": "Я эксперт и самостоятельно сделал всю систему.",
            "result": "Получился результат.",
            "source_evidence_id": "ev-1",
            "grounding_status": "grounded",
            "requires_human_review": True,
        }
    )

    assert any(issue.code == "possible_overclaim" for issue in report.issues)
