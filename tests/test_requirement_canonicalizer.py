import pytest

from app.services.requirement_canonicalizer import (
    canonicalize_requirement,
    canonicalize_requirements,
    requirement_is_user_facing_learning_topic,
    split_atomic_requirements,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        # Явные разделители пунктов (; | / •) — сплитим.
        ("Python / FastAPI", ["Python", "FastAPI"]),
        ("ведение договоров; претензионная работа", ["ведение договоров", "претензионная работа"]),
        ("МИС | ЭМК • маршрутизация пациентов", ["МИС", "ЭМК", "маршрутизация пациентов"]),
        # Легитимный список через запятую — сплитим на пункты.
        ("1С 8.3, Контур", ["1С 8.3", "Контур"]),
        # Запятая внутри фразы-предложения — НЕ новый пункт: обрубок
        # «связанными с сервисами» начинается с причастия → склеивается
        # обратно к «работа с инструментами». Раньше был обрубок-фрагмент
        # «Связанных с сервисами» как отдельное must_have-требование.
        ("работа с инструментами, связанными с сервисами", ["работа с инструментами, связанными с сервисами"]),
    ],
)
def test_split_atomic_requirements_normalizes_common_separators(
    value: str,
    expected: list[str],
) -> None:
    assert split_atomic_requirements(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Что", True),
        ("Требования", True),
        ("Обязанности", True),
        ("Жилыми", True),
        ("1С", False),
    ],
)
def test_canonicalize_requirement_marks_noise(value: str, expected: bool) -> None:
    assert canonicalize_requirement(value).is_noise is expected


@pytest.mark.parametrize(
    ("value", "display"),
    [
        ("python", "Python"),
        ("PYTHON", "Python"),
        ("Node.js", "Node.js"),
        ("ASP.NET", "ASP.NET"),
        ("Коммерческими или промышленными объектами", "Коммерческие проекты"),
        ("Жилыми объектами", "Жилые проекты"),
    ],
)
def test_canonicalize_requirement_builds_display(value: str, display: str) -> None:
    canonical = canonicalize_requirement(value)

    assert canonical.display == display
    assert not canonical.is_noise


@pytest.mark.parametrize(
    ("value", "display", "question_label", "summary_label", "confidence_label"),
    [
        (
            "Коммерческими или промышленными объектами",
            "Коммерческие проекты",
            "опыт управления коммерческими проектами",
            "",
            "Опыт управления коммерческими проектами",
        ),
        (
            "Жилыми объектами",
            "Жилые проекты",
            "опыт управления жилыми проектами",
            "",
            "Опыт управления жилыми проектами",
        ),
        ("Python", "Python", "Python", "Python", "Python"),
        (
            "договорная работа",
            "Договорная работа",
            "договорная работа",
            "Договорная работа",
            "Договорная работа",
        ),
    ],
)
def test_canonicalize_requirement_builds_surface_specific_labels(
    value: str,
    display: str,
    question_label: str,
    summary_label: str,
    confidence_label: str,
) -> None:
    canonical = canonicalize_requirement(value)

    assert canonical.display == display
    assert canonical.question_label == question_label
    assert canonical.summary_label == summary_label
    assert canonical.confidence_label == confidence_label


def test_canonicalize_requirements_dedupes_by_normalized_value() -> None:
    canonical_items = canonicalize_requirements(["Python", "python", "PYTHON"])

    assert [item.display for item in canonical_items] == ["Python"]


@pytest.mark.parametrize(
    "value",
    ["высшее", "опыт работы", "опыт работы от 1 года", "Жилыми"],
)
def test_requirement_is_user_facing_learning_topic_rejects_non_topics(value: str) -> None:
    assert not requirement_is_user_facing_learning_topic(value)
