from app.domain.requirement_normalization import (
    normalize_requirement_phrase,
    requirement_match_key,
)


def test_normalize_requirement_phrase_compacts_project_documentation() -> None:
    assert (
        normalize_requirement_phrase(
            "Проектная документация Проектный менеджмент Ведение проектной документации"
        )
        == "ведение проектной документации"
    )


def test_normalize_requirement_phrase_compacts_bim_processes() -> None:
    assert (
        normalize_requirement_phrase("Настройка BIM-процессов и координация проектирования")
        == "BIM-процессы"
    )


def test_normalize_requirement_phrase_compacts_expertise_interaction() -> None:
    assert (
        normalize_requirement_phrase("Взаимодействие с экспертизой и прохождение экспертизы")
        == "взаимодействие с экспертизой"
    )


def test_normalize_requirement_phrase_compacts_cross_functional_team() -> None:
    assert (
        normalize_requirement_phrase(
            "Команду архитекторов, инженеров, BIM-специалистов и управленцев"
        )
        == "управление межфункциональной проектной командой"
    )


def test_normalize_requirement_phrase_compacts_skill_bundle() -> None:
    assert (
        normalize_requirement_phrase("Деловая коммуникация Организаторские навыки")
        == "деловая коммуникация"
    )


def test_normalize_requirement_phrase_compacts_bim_company_context() -> None:
    assert (
        normalize_requirement_phrase(
            "Работу в проектной BIM-компании с реальными задачами и растущим объёмом проектов"
        )
        == "опыт BIM-проектирования"
    )


def test_requirement_match_key_maps_project_documentation_alias() -> None:
    assert requirement_match_key("Проектная документация") == "ведение проектной документации"
    assert requirement_match_key("ведение проектной документации") == "ведение проектной документации"
