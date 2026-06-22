from app.services.document_quality_service import DocumentQualityService
from app.domain.document_quality import (
    DocumentQualityRecommendation,
    DocumentQualityReport,
    ImprovementRoadmap,
    ImprovementRoadmapStep,
)


def test_resume_quality_scores_good_document() -> None:
    service = DocumentQualityService()

    report = service.evaluate_resume(
        content_json={
            "sections": {
                "matched_keywords": ["1С", "НДС", "первичная документация"],
                "missing_keywords": ["банк-клиент"],
                "skills": ["1С:Бухгалтерия", "НДС", "Первичная документация"],
                "selected_achievements": [
                    {
                        "title": "Сократила срок подготовки отчетов на 20%",
                        "action": "Оптимизировала подготовку отчетов",
                        "result": "Сократила сроки",
                        "metric_text": "20%",
                        "fact_status": "confirmed",
                    }
                ],
                "selected_evidence_ids": ["ev-1"],
                "vacancy_aligned_summary": (
                    "Бухгалтер с опытом работы с первичной документацией, "
                    "НДС и сверкой взаиморасчётов."
                ),
            }
        },
        rendered_text="Бухгалтер\nОпыт работы\nНавыки: 1С, НДС",
    )

    assert report.document_kind == "resume"
    assert report.score >= 70
    assert report.grade in {"good", "excellent"}


def test_resume_score_breakdown_is_present() -> None:
    service = DocumentQualityService()

    report = service.evaluate_resume(
        content_json={
            "sections": {
                "matched_keywords": ["Figma"],
                "skills": ["Figma"],
                "selected_achievements": [],
            }
        },
        rendered_text="Designer",
    )

    payload = report.as_dict()

    assert "score_breakdown" in payload
    assert any(
        item["code"] == "vacancy_alignment"
        for item in payload["score_breakdown"]
    )
    assert any(
        item["label"] == "Соответствие вакансии"
        for item in payload["score_breakdown"]
    )
    assert all("missing_points" in item for item in payload["score_breakdown"])


def test_cover_letter_detects_generic_closing() -> None:
    service = DocumentQualityService()

    report = service.evaluate_cover_letter(
        content_json={
            "sections": {
                "matched_keywords": ["закупки"],
                "missing_keywords": [],
                "selected_achievements": [],
                "evidence_relevance": [],
            }
        },
        rendered_text=(
            "Здравствуйте! Откликаюсь на позицию. "
            "Готов применять накопленный опыт в области закупок. "
            "Буду рад обсудить, чем мой опыт может быть полезен."
        ),
    )

    assert any(issue.code == "generic_closing" for issue in report.issues)
    assert report.metrics["ai_phrase_density"] < 15


def test_cover_letter_duplication_penalty() -> None:
    service = DocumentQualityService()

    text = (
        "Работал с первичной документацией, НДС, актами сверки и банк-клиентом. "
        "Готов применять опыт в бухгалтерии."
    )

    report = service.evaluate_cover_letter(
        content_json={
            "sections": {
                "matched_keywords": ["НДС"],
                "missing_keywords": [],
                "selected_achievements": [],
                "evidence_relevance": [],
            }
        },
        rendered_text=text,
        resume_text=text,
    )

    assert report.metrics["duplication"] < 8
    assert any(issue.code == "resume_letter_duplication" for issue in report.issues)


def test_quality_report_uses_human_readable_labels() -> None:
    service = DocumentQualityService()

    report = service.evaluate_cover_letter(
        content_json={
            "sections": {
                "matched_keywords": ["закупки"],
                "missing_keywords": [],
                "selected_achievements": [],
                "evidence_relevance": [],
            }
        },
        rendered_text=(
            "Здравствуйте! Откликаюсь на позицию. "
            "Готов применять накопленный опыт в области закупок. "
            "Буду рад обсудить, чем мой опыт может быть полезен."
        ),
    )

    assert "generic_closing" not in report.improvements
    assert "Сделать финальный абзац более персонализированным" in report.improvements
    assert all("_" not in strength for strength in report.strengths)


def test_quality_report_adds_fallback_improvement_for_low_metric_score() -> None:
    service = DocumentQualityService()

    report = service.evaluate_resume(
        content_json={
            "sections": {
                "matched_keywords": [],
                "missing_keywords": ["Kubernetes"],
                "skills": [],
                "selected_achievements": [
                    {
                        "title": "Оптимизировал backend API на FastAPI",
                        "action": "Оптимизировал backend API",
                        "result": "Ускорил обработку запросов",
                        "metric_text": "20%",
                    }
                ],
            }
        },
        rendered_text="Backend developer\nFastAPI API optimization",
    )

    assert report.score < 70
    assert report.improvements == [
        "Усилить покрытие требований вакансии и доказательную базу"
    ]


def test_resume_quality_recommendations_explain_low_alignment() -> None:
    service = DocumentQualityService()

    report = service.evaluate_resume(
        content_json={
            "sections": {
                "matched_keywords": [],
                "missing_keywords": ["Adobe Photoshop", "CorelDRAW"],
                "skills": ["Figma"],
                "selected_achievements": [],
            }
        },
        rendered_text="Дизайнер с опытом подготовки макетов.",
    )

    assert report.recommendations
    assert any(
        item.code == "improve_vacancy_alignment"
        for item in report.recommendations
    )
    payload = report.as_dict()
    assert "recommendations" in payload
    recommendation_payload = next(
        item
        for item in payload["recommendations"]
        if item["code"] == "improve_vacancy_alignment"
    )
    diagnostics = recommendation_payload["details"]["vacancy_gap_diagnostics"]

    assert diagnostics["missing_keywords"] == ["Adobe Photoshop", "CorelDRAW"]
    assert diagnostics["total_missing"] == 2
    assert diagnostics["priority"] == "medium"
    assert diagnostics["actions"] == [
        "Проверить, есть ли этот навык или обязанность в реальном опыте кандидата",
        "Если опыт подтверждён — добавить конкретный пример",
        "Если опыта нет — не добавлять требование как факт",
    ]
    assert recommendation_payload["impact"] == {
        "metric": "vacancy_alignment",
        "potential_gain": 25,
    }


def test_cover_letter_quality_recommendations_explain_generic_closing() -> None:
    service = DocumentQualityService()

    report = service.evaluate_cover_letter(
        content_json={
            "sections": {
                "matched_keywords": ["закупки"],
                "missing_keywords": [],
                "selected_achievements": [],
                "evidence_relevance": [],
            }
        },
        rendered_text=(
            "Здравствуйте! Откликаюсь на позицию. "
            "Готов применять накопленный опыт в области закупок. "
            "Буду рад обсудить, чем мой опыт может быть полезен."
        ),
    )

    assert any(
        item.code == "rewrite_generic_closing"
        for item in report.recommendations
    )


def test_resume_recommendations_include_achievement_diagnostics() -> None:
    service = DocumentQualityService()

    report = service.evaluate_resume(
        content_json={
            "sections": {
                "matched_keywords": ["Figma"],
                "missing_keywords": ["Adobe Photoshop"],
                "skills": ["Figma"],
                "selected_achievements": [
                    {
                        "title": "Подготовка макетов для печати",
                        "action": "",
                        "result": "",
                        "metric_text": "",
                    },
                    {
                        "title": "Оптимизировал процесс согласования макетов",
                        "action": "Оптимизировал процесс согласования макетов",
                        "result": "Согласование стало быстрее",
                        "metric_text": "",
                    },
                ],
            }
        },
        rendered_text="Дизайнер. Подготовка макетов.",
    )

    recommendation = next(
        item for item in report.recommendations
        if item.code == "improve_achievements"
    )

    assert any(
        "Диагностика достижений: всего 2" in action
        for action in recommendation.actions
    )
    assert any(
        "без метрики 2" in action
        for action in recommendation.actions
    )

    payload = report.as_dict()
    recommendation_payload = next(
        item for item in payload["recommendations"]
        if item["code"] == "improve_achievements"
    )
    diagnostics = recommendation_payload["details"]["achievement_diagnostics"]

    assert diagnostics["total"] == 2
    assert diagnostics["without_metric"] == 2
    assert diagnostics["problem_achievements"][0]["title"] == "Подготовка макетов для печати"
    assert diagnostics["problem_achievements"][0]["missing"] == [
        "action",
        "result",
        "metric",
    ]
    assert diagnostics["problem_achievements"][0]["severity"] == 3
    assert diagnostics["problem_achievements"][0]["priority_label"] == "Высокий приоритет"

    problem = diagnostics["problem_achievements"][0]
    assert "questions" in problem
    assert "Что именно вы сделали лично?" in problem["questions"]
    assert "Что изменилось после вашей работы?" in problem["questions"]
    assert (
        "Можно ли подтвердить результат числом, сроком, объёмом или процентом?"
        in problem["questions"]
    )

    assert diagnostics["problem_achievements"][0]["rewrite_hint"] == (
        "Подготовка макетов для печати → уточнить личный вклад "
        "→ добавить подтверждённый результат → добавить метрику, если она реально известна"
    )

    assert diagnostics["problem_achievements"][0]["severity"] >= diagnostics["problem_achievements"][-1]["severity"]


def test_achievement_diagnostics_sort_problem_achievements_by_severity() -> None:
    service = DocumentQualityService()

    diagnostics = service._achievement_diagnostics(
        {
            "selected_achievements": [
                {
                    "title": "Сократила сроки подготовки макетов на 30%",
                    "action": "Сократила сроки подготовки макетов",
                    "result": "",
                    "metric_text": "30%",
                },
                {
                    "title": "Участвовала в ребрендинге продуктовой линейки",
                    "action": "",
                    "result": "",
                    "metric_text": "",
                },
            ]
        }
    )

    assert diagnostics["problem_achievements"][0]["title"] == (
        "Участвовала в ребрендинге продуктовой линейки"
    )
    assert diagnostics["problem_achievements"][0]["severity"] == 3


def test_resume_recommendations_include_vacancy_gap_diagnostics() -> None:
    service = DocumentQualityService()

    report = service.evaluate_resume(
        content_json={
            "sections": {
                "matched_keywords": [],
                "missing_keywords": [
                    "Adobe Photoshop",
                    "CorelDRAW",
                ],
                "skills": ["Figma"],
                "selected_achievements": [],
            }
        },
        rendered_text="Дизайнер",
    )

    payload = report.as_dict()

    recommendation = next(
        item
        for item in payload["recommendations"]
        if item["code"] == "improve_vacancy_alignment"
    )

    diagnostics = recommendation["details"]["vacancy_gap_diagnostics"]

    assert diagnostics["total_missing"] == 2
    assert diagnostics["missing_keywords"] == [
        "Adobe Photoshop",
        "CorelDRAW",
    ]
    assert diagnostics["gaps"][0] == {
        "keyword": "Adobe Photoshop",
        "status": "not_confirmed",
        "label": "Не подтверждено профилем",
        "safe_to_add": False,
        "importance": "high",
        "coverage_opportunity": 2,
        "reason": "Требование есть в вакансии, но пока не найдено в данных профиля.",
        "matched_sources": [],
    }
    assert diagnostics["gaps"][0]["importance"] == "high"


def test_improvement_roadmap_ranks_recommendations_by_gain() -> None:
    service = DocumentQualityService()

    roadmap = service._build_improvement_roadmap(
        score=62,
        recommendations=[
            DocumentQualityRecommendation(
                code="improve_vacancy_alignment",
                title="Усилить соответствие вакансии",
                why="",
                impact={"potential_gain": 25},
            ),
            DocumentQualityRecommendation(
                code="improve_achievements",
                title="Усилить достижения",
                why="",
                impact={"potential_gain": 8},
            ),
            DocumentQualityRecommendation(
                code="improve_ats_quality",
                title="Улучшить ATS качество",
                why="",
                impact={"potential_gain": 3},
            ),
            DocumentQualityRecommendation(
                code="ignore_zero_gain",
                title="Игнорировать",
                why="",
                impact={"potential_gain": 0},
            ),
        ],
    )

    assert roadmap is not None
    assert roadmap.current_score == 62
    assert roadmap.projected_score == 87
    assert [step.order for step in roadmap.steps] == [1, 2, 3]
    assert [step.title for step in roadmap.steps] == [
        "Усилить соответствие вакансии",
        "Усилить достижения",
        "Улучшить ATS качество",
    ]
    assert [step.expected_gain for step in roadmap.steps] == [25, 8, 3]
    assert [step.recommendation_code for step in roadmap.steps] == [
        "improve_vacancy_alignment",
        "improve_achievements",
        "improve_ats_quality",
    ]

    assert roadmap.projected_score == 87


def test_quality_report_includes_roadmap_payload() -> None:
    report = DocumentQualityReport(
        document_kind="resume",
        score=67,
        grade="good",
        roadmap=ImprovementRoadmap(
            current_score=67,
            projected_score=92,
            steps=[
                ImprovementRoadmapStep(
                    order=1,
                    title="Усилить соответствие вакансии",
                    expected_gain=25,
                    recommendation_code="improve_vacancy_alignment",
                ),
                ImprovementRoadmapStep(
                    order=2,
                    title="Усилить достижения",
                    expected_gain=8,
                    recommendation_code="improve_achievements",
                ),
            ],
        ),
    )

    payload = report.as_dict()

    assert payload["score"] == 67
    assert payload["roadmap"] == {
        "current_score": 67,
        "projected_score": 92,
        "steps": [
            {
                "order": 1,
                "title": "Усилить соответствие вакансии",
                "expected_gain": 25,
            },
            {
                "order": 2,
                "title": "Усилить достижения",
                "expected_gain": 8,
            },
        ],
    }


def test_vacancy_gap_classification_confirms_profile_match_from_skills() -> None:
    service = DocumentQualityService()

    diagnostics = service._vacancy_gap_diagnostics(
        ["Adobe Photoshop"],
        sections={
            "skills": ["Adobe Photoshop", "Figma"],
        },
    )

    assert diagnostics["gaps"][0] == {
        "keyword": "Adobe Photoshop",
        "status": "confirmed_in_profile",
        "label": "Найдено в профиле",
        "safe_to_add": True,
        "importance": "high",
        "coverage_opportunity": 10,
        "reason": (
            "Требование есть в вакансии и найдено в данных профиля. "
            "Можно усилить документ, если формулировка не искажает опыт."
        ),
        "matched_sources": ["skills"],
    }


def test_vacancy_gap_importance_detects_key_tools() -> None:
    service = DocumentQualityService()

    assert service._gap_importance("Adobe Photoshop") == "high"
    assert service._gap_importance("CorelDRAW") == "high"
    assert service._gap_importance("Подготовка макетов к печати") == "medium"


def test_vacancy_gap_profile_match_detects_achievements() -> None:
    service = DocumentQualityService()

    sources = service._gap_profile_match(
        "CorelDRAW",
        {
            "selected_achievements": [
                {
                    "title": "Работа в CorelDraw и подготовка макетов",
                    "action": "",
                    "result": "",
                    "metric_text": "",
                }
            ]
        },
    )

    assert sources == ["selected_achievements"]


def test_vacancy_gap_coverage_opportunity_scores() -> None:
    service = DocumentQualityService()

    assert service._gap_coverage_opportunity(
        importance="high",
        safe_to_add=True,
    ) == 10
    assert service._gap_coverage_opportunity(
        importance="medium",
        safe_to_add=True,
    ) == 5
    assert service._gap_coverage_opportunity(
        importance="high",
        safe_to_add=False,
    ) == 2
    assert service._gap_coverage_opportunity(
        importance="medium",
        safe_to_add=False,
    ) == 1


def test_vacancy_gap_classification_marks_profile_confirmed_skill_safe_to_add() -> None:
    service = DocumentQualityService()

    report = service.evaluate_resume(
        content_json={
            "sections": {
                "matched_keywords": [],
                "missing_keywords": ["Adobe Photoshop", "CorelDRAW"],
                "skills": ["Adobe Photoshop", "Figma"],
                "selected_achievements": [],
            }
        },
        rendered_text="Дизайнер",
    )

    payload = report.as_dict()
    recommendation = next(
        item
        for item in payload["recommendations"]
        if item["code"] == "improve_vacancy_alignment"
    )
    gaps = recommendation["details"]["vacancy_gap_diagnostics"]["gaps"]

    photoshop = next(item for item in gaps if item["keyword"] == "Adobe Photoshop")
    coreldraw = next(item for item in gaps if item["keyword"] == "CorelDRAW")

    assert photoshop["status"] == "confirmed_in_profile"
    assert photoshop["safe_to_add"] is True
    assert photoshop["matched_sources"] == ["skills"]
    assert photoshop["coverage_opportunity"] == 10

    assert coreldraw["status"] == "not_confirmed"
    assert coreldraw["safe_to_add"] is False
    assert coreldraw["matched_sources"] == []
    assert coreldraw["coverage_opportunity"] == 2
