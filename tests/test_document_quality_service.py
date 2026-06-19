from app.services.document_quality_service import DocumentQualityService


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
