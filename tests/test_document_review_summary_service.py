from __future__ import annotations

from types import SimpleNamespace

from app.services.document_quality_service import DocumentQualityService
from app.services.document_review_summary_service import DocumentReviewSummaryService


class _FakeReadinessGateService:
    def evaluate_document_readiness(self, document):
        return SimpleNamespace(
            ready=True,
            blockers=[],
            warnings=[],
            score=0.9,
        )


def test_document_review_summary_includes_resume_quality() -> None:
    service = DocumentReviewSummaryService(
        readiness_gate_service=_FakeReadinessGateService(),
        quality_service=DocumentQualityService(),
    )
    document = SimpleNamespace(
        document_kind="resume",
        content_json={
            "sections": {
                "matched_keywords": ["1С", "НДС"],
                "missing_keywords": [],
                "skills": ["1С:Бухгалтерия", "НДС"],
                "selected_achievements": [
                    {
                        "id": "ach-1",
                        "title": "Сократила срок подготовки отчетов на 20%",
                        "action": "Оптимизировала подготовку отчетов",
                        "result": "Сократила сроки",
                        "metric_text": "20%",
                        "fact_status": "confirmed",
                    }
                ],
                "selected_evidence_ids": ["ev-1"],
                "vacancy_aligned_summary": (
                    "Бухгалтер с опытом работы с НДС и первичной документацией."
                ),
            }
        },
        rendered_text="Бухгалтер с опытом работы с НДС и первичной документацией.",
    )

    summary = service.build_summary(document)

    assert "quality" in summary
    assert summary["quality"]["document_kind"] == "resume"
    assert isinstance(summary["quality"]["score"], int)
    assert summary["quality"]["grade"] in {"excellent", "good", "needs_work", "weak"}
    assert isinstance(summary["quality"]["metrics"], dict)


def test_document_review_summary_includes_cover_letter_quality() -> None:
    service = DocumentReviewSummaryService()
    document = SimpleNamespace(
        document_kind="cover_letter",
        review_status="draft",
        is_active=False,
        content_json={
            "sections": {
                "matched_keywords": ["закупки"],
                "missing_keywords": [],
                "selected_achievements": [
                    {
                        "id": "ach-1",
                        "title": "Оптимизировал закупочный процесс",
                        "action": "Оптимизировал закупочный процесс",
                        "result": "Снизил сроки согласования",
                        "metric_text": "",
                        "fact_status": "confirmed",
                    }
                ],
                "evidence_relevance": [
                    {
                        "evidence_id": "ev-1",
                        "title": "Опыт закупок",
                    }
                ],
            },
            "meta": {},
        },
        rendered_text=(
            "Здравствуйте! Откликаюсь на позицию. "
            "Готов применять накопленный опыт в области закупок. "
            "Буду рад обсудить, чем мой опыт может быть полезен."
        ),
    )

    summary = service.build_summary(document)

    assert "quality" in summary
    assert summary["quality"]["document_kind"] == "cover_letter"
    assert isinstance(summary["quality"]["score"], int)
    assert summary["quality"]["grade"] in {"excellent", "good", "needs_work", "weak"}
    assert isinstance(summary["quality"]["metrics"], dict)
    assert "relevance" in summary["quality"]["metrics"]
    assert "ai_phrase_density" in summary["quality"]["metrics"]
