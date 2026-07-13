from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.case_prep import STABLE_CASE_TYPES, assert_no_fabricated_specifics
from app.services.case_prep_service import CasePrepService


pytestmark = pytest.mark.asyncio


def _ev(evidence_id, title, score, fact_status, strength="strong") -> dict:
    return {
        "evidence_id": evidence_id,
        "title": title,
        "reason": f"skills overlap; strength={strength}; fact_status={fact_status}",
        "score": score,
        "fact_status": fact_status,
        "evidence_strength": strength,
        "star_preview": {},
        "snippet_text": "",
    }


class _StubVacancyFitService:
    """Возвращает заранее заготовленный fit-словарь."""

    def __init__(self, fit: dict) -> None:
        self._fit = fit
        self.calls: list[dict] = []

    async def build_vacancy_fit(self, session, *, vacancy_id, user_id) -> dict:
        self.calls.append({"vacancy_id": vacancy_id, "user_id": user_id})
        return self._fit


class _FailingVacancyFitService404:
    async def build_vacancy_fit(self, session, *, vacancy_id, user_id) -> dict:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="vacancy not found")


class _FailingVacancyFitService400:
    async def build_vacancy_fit(self, session, *, vacancy_id, user_id) -> dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="vacancy analysis not found; run vacancy analysis first",
        )


def _fit_with_evidence() -> dict:
    """Fit с одним must-have requirement и 4 supporting_evidence разного fact_status."""
    supporting = [
        _ev(uuid4(), "Stakeholder communication", 90.0, "confirmed", "strong"),
        _ev(uuid4(), "Needs confirmation snippet", 85.0, "needs_confirmation", "medium"),
        _ev(uuid4(), "User-provided note", 80.0, "user_provided", "medium"),
        _ev(uuid4(), "Another confirmed", 70.0, "confirmed", "weak"),
    ]
    return {
        "vacancy_id": uuid4(),
        "requirements": [
            {
                "requirement": "Senior system design leadership",
                "scope": "must_have",
                "severity": "critical",
                "coverage_level": "none",
                "reason": "No confirmed evidence or profile overlap found.",
                "evidence_ids": [str(m["evidence_id"]) for m in supporting],
                "supporting_evidence": supporting,
            }
        ],
        "evidence_coverage": {
            "required": ["Senior system design leadership"],
            "strong": [],
            "medium": [],
            "missing": [
                {
                    "requirement": "Senior system design leadership",
                    "scope": "must_have",
                    "severity": "critical",
                    "supporting_evidence": supporting,
                }
            ],
        },
        "gap_severity": "critical",
    }


async def test_build_case_set_selects_system_design_for_senior_leadership() -> None:
    service = CasePrepService(vacancy_fit_service=_StubVacancyFitService(_fit_with_evidence()))
    report = await service.build_case_set(
        session=None,
        user_id=uuid4(),
        vacancy_id=uuid4(),
    )
    types = [c["case_type"] for c in report["cases"]]
    assert "system_design" in types
    for t in types:
        assert t in STABLE_CASE_TYPES


async def test_build_case_set_recommended_evidence_excludes_needs_confirmation() -> None:
    service = CasePrepService(vacancy_fit_service=_StubVacancyFitService(_fit_with_evidence()))
    report = await service.build_case_set(session=None, user_id=uuid4(), vacancy_id=uuid4())
    for case in report["cases"]:
        for ev in case["recommended_evidence"]:
            assert ev["fact_status"] in {"confirmed", "user_provided"}


async def test_build_case_set_recommended_evidence_top_two() -> None:
    service = CasePrepService(vacancy_fit_service=_StubVacancyFitService(_fit_with_evidence()))
    report = await service.build_case_set(session=None, user_id=uuid4(), vacancy_id=uuid4())
    # system_design-кейс имеет якорем must-have requirement с 4 supporting_evidence,
    # из них 3 confirmed/user_provided → top-2.
    sd_case = next(c for c in report["cases"] if c["case_type"] == "system_design")
    assert len(sd_case["recommended_evidence"]) == 2
    # Порядок сохранён (по score desc после фильтра).
    assert sd_case["recommended_evidence"][0]["fact_status"] == "confirmed"
    assert sd_case["recommended_evidence"][1]["fact_status"] == "user_provided"


async def test_build_case_set_propagates_404_for_foreign_vacancy() -> None:
    service = CasePrepService(vacancy_fit_service=_FailingVacancyFitService404())
    with pytest.raises(HTTPException) as exc:
        await service.build_case_set(session=None, user_id=uuid4(), vacancy_id=uuid4())
    assert exc.value.status_code == status.HTTP_404_NOT_FOUND


async def test_build_case_set_falls_back_to_empty_report_on_400() -> None:
    service = CasePrepService(vacancy_fit_service=_FailingVacancyFitService400())
    report = await service.build_case_set(session=None, user_id=uuid4(), vacancy_id=uuid4())
    assert report["cases"] == []
    assert report["meta"]["total"] == 0
    assert report["meta"]["reason"] == "vacancy_analysis_or_profile_missing"
    assert report["provenance"]["requires_human_review"] is True


async def test_build_case_set_provenance_requires_human_review_and_sources() -> None:
    service = CasePrepService(vacancy_fit_service=_StubVacancyFitService(_fit_with_evidence()))
    report = await service.build_case_set(session=None, user_id=uuid4(), vacancy_id=uuid4())
    assert report["provenance"]["requires_human_review"] is True
    assert report["provenance"]["sources"] == ["vacancy_fit"]


async def test_build_case_set_serializes_vacancy_id_as_str() -> None:
    vacancy_id = uuid4()
    service = CasePrepService(vacancy_fit_service=_StubVacancyFitService(_fit_with_evidence()))
    report = await service.build_case_set(session=None, user_id=uuid4(), vacancy_id=vacancy_id)
    assert report["vacancy_id"] == str(vacancy_id)


async def test_build_case_set_has_no_fabricated_specifics() -> None:
    from app.domain.case_prep import PracticeCase

    service = CasePrepService(vacancy_fit_service=_StubVacancyFitService(_fit_with_evidence()))
    report = await service.build_case_set(session=None, user_id=uuid4(), vacancy_id=uuid4())
    cases = [
        PracticeCase(
            case_id=c["case_id"],
            case_type=c["case_type"],
            title=c["title"],
            prompt=c["prompt"],
            framework=c["framework"],
            time_guidance=c["time_guidance"],
        )
        for c in report["cases"]
    ]
    assert assert_no_fabricated_specifics(cases) is True


async def test_build_case_set_meta_counts_match_cases() -> None:
    service = CasePrepService(vacancy_fit_service=_StubVacancyFitService(_fit_with_evidence()))
    report = await service.build_case_set(session=None, user_id=uuid4(), vacancy_id=uuid4())
    meta = report["meta"]
    assert meta["total"] == len(report["cases"])
    for case_type, count in meta["case_type_counts"].items():
        assert sum(1 for c in report["cases"] if c["case_type"] == case_type) == count
    assert meta["has_critical_gap"] is True


async def test_build_case_set_empty_requirements_yields_behavioral_case() -> None:
    fit = {
        "vacancy_id": uuid4(),
        "requirements": [],
        "evidence_coverage": {"required": [], "strong": [], "medium": [], "missing": []},
        "gap_severity": "minor",
    }
    service = CasePrepService(vacancy_fit_service=_StubVacancyFitService(fit))
    report = await service.build_case_set(session=None, user_id=uuid4(), vacancy_id=uuid4())
    assert [c["case_type"] for c in report["cases"]] == ["behavioral_case"]