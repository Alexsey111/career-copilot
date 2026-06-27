from app.services.semantic_requirement_matcher import SemanticRequirementMatcher


def test_pc_user_matches_medical_information_systems() -> None:
    matcher = SemanticRequirementMatcher()

    result = matcher.match(
        "Пользователь ПК",
        ["Электронные медицинские системы"],
    )

    assert result.matched is True
    assert result.confidence >= 0.8


def test_pc_user_matches_emr_evidence() -> None:
    matcher = SemanticRequirementMatcher()

    result = matcher.match(
        "Пользователь ПК",
        ["Участвовал во внедрении электронной медкарты"],
    )

    assert result.matched is True


def test_communication_matches_consultations() -> None:
    matcher = SemanticRequirementMatcher()

    result = matcher.match(
        "коммуникация",
        ["Провёл более 5000 консультаций"],
    )

    assert result.matched is True


def test_rest_api_matches_fastapi() -> None:
    matcher = SemanticRequirementMatcher()

    result = matcher.match(
        "REST API",
        ["FastAPI"],
    )

    assert result.matched is True


def test_contract_law_matches_contract_work() -> None:
    matcher = SemanticRequirementMatcher()

    result = matcher.match(
        "Договорное право",
        ["Подготовила более 250 договоров"],
    )

    assert result.matched is True


def test_design_editors_match_photoshop() -> None:
    matcher = SemanticRequirementMatcher()

    result = matcher.match(
        "Графические редакторы",
        ["Adobe Photoshop"],
    )

    assert result.matched is True


def test_warehouse_logistics_matches_wms() -> None:
    matcher = SemanticRequirementMatcher()

    result = matcher.match(
        "Складская логистика",
        ["WMS"],
    )

    assert result.matched is True


def test_unrelated_terms_do_not_match() -> None:
    matcher = SemanticRequirementMatcher()

    result = matcher.match(
        "Договорное право",
        ["Adobe Photoshop"],
    )

    assert result.matched is False