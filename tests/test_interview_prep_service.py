from app.services.interview_prep_service import InterviewPrepService


def test_build_question_summary_counts_categories_and_evidence() -> None:
    service = InterviewPrepService()

    summary = service._build_question_summary(
        [
            {
                "category": "technical",
                "recommended_evidence_ids": ["ev-1"],
                "requires_careful_answer": False,
            },
            {
                "category": "gap-risk",
                "recommended_evidence": [{"achievement_id": "ev-2"}],
                "requires_careful_answer": True,
            },
            {
                "category": "behavioral",
                "recommended_evidence_ids": [],
                "requires_careful_answer": False,
            },
        ]
    )

    assert summary == {
        "total": 3,
        "by_category": {
            "technical": 1,
            "gap-risk": 1,
            "behavioral": 1,
        },
        "careful_answer_count": 1,
        "with_evidence_count": 2,
    }
