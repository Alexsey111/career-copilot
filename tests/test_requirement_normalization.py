from app.domain.requirement_normalization import (
    classify_requirement_phrase,
    is_ignored_requirement_header,
    normalize_requirement_phrase,
    normalize_requirement_phrases,
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


def test_normalize_requirement_phrase_compacts_long_legislation_list() -> None:
    assert (
        normalize_requirement_phrase(
            "знание Конституции РФ, Устава Алтайского края, "
            "законодательства о муниципальной службе"
        )
        == "знание профильного законодательства"
    )


def test_normalize_requirement_phrase_compacts_generic_legal_phrases() -> None:
    assert (
        normalize_requirement_phrase("наличие навыков нормотворческой деятельности")
        == "нормотворческая деятельность"
    )
    assert (
        normalize_requirement_phrase("ведения деловых переговоров")
        == "ведение переговоров"
    )
    assert (
        normalize_requirement_phrase("владение официально-деловым стилем")
        == "официально-деловой стиль"
    )


def test_ignored_requirement_headers_detects_split_headings() -> None:
    assert is_ignored_requirement_header("к квалификации")
    assert is_ignored_requirement_header("Образование:")
    assert is_ignored_requirement_header("Профессиональные")
    assert is_ignored_requirement_header("навыки:")


def test_classify_requirement_phrase_detects_core_requirement_types() -> None:
    assert classify_requirement_phrase("Высшее образование") == "education"
    assert classify_requirement_phrase("Диплом о высшем медицинском образовании") == "education"
    assert classify_requirement_phrase("сертификат специалиста") == "certification"
    assert classify_requirement_phrase("Python") == "skill"
    assert classify_requirement_phrase("управление полевой командой") == "competency"


def test_normalize_requirement_phrases_condenses_retail_bundle() -> None:
    assert normalize_requirement_phrases(
        "Опыт: от 2 лет в сфере мерчандайзинга, управление командой "
        "торговых представителей, розничные продажи FMCG"
    ) == [
        "мерчандайзинг",
        "управление полевой командой",
        "розничные продажи",
        "FMCG",
    ]


def test_normalize_requirement_phrase_compacts_plumbing_experience() -> None:
    assert (
        normalize_requirement_phrase("Опыт работы в данном направлении не менее 3 лет")
        == "опыт работы сантехником от 3 лет"
    )
    assert (
        normalize_requirement_phrase(
            "Готовность работать с инженерными коммуникациями пищевого производства"
        )
        == "обслуживание инженерных систем"
    )


def test_normalize_requirement_phrases_splits_personal_traits() -> None:
    assert normalize_requirement_phrases(
        "Ответственность, аккуратность, внимательность"
    ) == [
        "ответственность",
        "аккуратность",
        "внимательность",
    ]
