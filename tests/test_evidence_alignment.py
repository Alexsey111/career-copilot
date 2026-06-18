from app.domain.evidence_alignment import (
    humanize_experience_phrase,
    polish_summary_evidence_phrase,
)


def test_polish_summary_evidence_phrase_compacts_project_reporting() -> None:
    assert (
        polish_summary_evidence_phrase("систему проектной отчётности")
        == "внедрения системы проектной отчётности"
    )


def test_humanize_experience_phrase_supports_shared_grammar_cases() -> None:
    assert humanize_experience_phrase("Подготовка договоров") == "подготовки договоров"
    assert (
        humanize_experience_phrase(
            "Подготовка договоров",
            grammatical_case="instrumental",
        )
        == "подготовкой договоров"
    )
    assert humanize_experience_phrase("Работа в 1С:Бухгалтерия") == "работы в 1С:Бухгалтерия"
    assert (
        humanize_experience_phrase(
            "Участие в подготовке отчётности",
            grammatical_case="instrumental",
        )
        == "участием в подготовке отчётности"
    )


def test_polish_summary_evidence_phrase_builds_legal_summary_segments() -> None:
    assert (
        polish_summary_evidence_phrase(
            "Подготовка договоров Судебное сопровождение Консультирование клиентов"
        )
        == "подготовки договоров, судебного сопровождения, консультирования клиентов"
    )


def test_polish_summary_evidence_phrase_inflects_single_legal_phrase() -> None:
    assert polish_summary_evidence_phrase("Подготовка договоров") == "подготовки договоров"
    assert polish_summary_evidence_phrase("Судебное сопровождение") == "судебного сопровождения"
    assert (
        polish_summary_evidence_phrase("Консультирование клиентов")
        == "консультирования клиентов"
    )


def test_polish_summary_evidence_phrase_builds_accounting_summary_segments() -> None:
    assert (
        polish_summary_evidence_phrase(
            "Ведение первичной бухгалтерской документации "
            "Работа с актами и счетами "
            "Сверка взаиморасчетов с контрагентами"
        )
        == "ведения первичной бухгалтерской документации, "
        "работы с актами и счетами, "
        "сверки взаиморасчётов с контрагентами"
    )


def test_polish_summary_evidence_phrase_inflects_single_accounting_phrase() -> None:
    assert (
        polish_summary_evidence_phrase("Ведение первичной бухгалтерской документации")
        == "ведения первичной бухгалтерской документации"
    )
    assert (
        polish_summary_evidence_phrase("Работа с актами")
        == "работы с актами и счетами"
    )
    assert (
        polish_summary_evidence_phrase("Сверка взаиморасчетов с контрагентами")
        == "сверки взаиморасчётов с контрагентами"
    )
    assert (
        polish_summary_evidence_phrase("Подготовка платежных поручений")
        == "подготовки платёжных поручений"
    )


def test_polish_summary_evidence_phrase_builds_supervisor_summary_segments() -> None:
    assert (
        polish_summary_evidence_phrase(
            "Управление сменой 25 сотрудников "
            "Контроль приемки и отгрузки "
            "Работа с планограммами"
        )
        == "управления сменой 25 сотрудников, "
        "контроля приёмки и отгрузки, "
        "работы с планограммами"
    )


def test_polish_summary_evidence_phrase_inflects_single_supervisor_phrase() -> None:
    assert (
        polish_summary_evidence_phrase("Управление сменой 25 сотрудников")
        == "управления сменой 25 сотрудников"
    )
    assert (
        polish_summary_evidence_phrase("Контроль приемки и отгрузки")
        == "контроля приёмки и отгрузки"
    )
    assert (
        polish_summary_evidence_phrase("Контроль выкладки товара")
        == "контроля выкладки товаров"
    )


def test_polish_summary_evidence_phrase_builds_warehouse_summary_segments() -> None:
    assert (
        polish_summary_evidence_phrase(
            "Организация складских процессов "
            "Приемка и отгрузка товаров "
            "Комплектация заказов"
        )
        == "организации складских процессов, "
        "приёмки и отгрузки товаров, "
        "комплектации заказов"
    )


def test_polish_summary_evidence_phrase_builds_logistics_summary_segments() -> None:
    assert (
        polish_summary_evidence_phrase(
            "Планирование маршрутов "
            "Координация доставки "
            "Взаимодействие с перевозчиками"
        )
        == "планирования маршрутов, "
        "координации доставки, "
        "взаимодействия с перевозчиками"
    )


def test_humanize_experience_phrase_technical_actions_genitive() -> None:
    """Проверка склонения технических действий в родительный падеж."""
    assert humanize_experience_phrase("Монтаж") == "монтажа"
    assert humanize_experience_phrase("Обслуживание") == "обслуживания"
    assert humanize_experience_phrase("Замена") == "замены"
    assert humanize_experience_phrase("Ремонт") == "ремонта"
    assert humanize_experience_phrase("Установка") == "установки"
    assert humanize_experience_phrase("Проведение") == "проведения"


def test_humanize_experience_phrase_technical_actions_instrumental() -> None:
    """Проверка склонения технических действий в творительный падеж."""
    assert (
        humanize_experience_phrase("Монтаж", grammatical_case="instrumental")
        == "монтажом"
    )
    assert (
        humanize_experience_phrase("Обслуживание", grammatical_case="instrumental")
        == "обслуживанием"
    )
    assert (
        humanize_experience_phrase("Замена", grammatical_case="instrumental")
        == "заменой"
    )
    assert (
        humanize_experience_phrase("Ремонт", grammatical_case="instrumental")
        == "ремонтом"
    )
    assert (
        humanize_experience_phrase("Установка", grammatical_case="instrumental")
        == "установкой"
    )
    assert (
        humanize_experience_phrase("Проведение", grammatical_case="instrumental")
        == "проведением"
    )


def test_humanize_experience_phrase_keeps_case_for_multiple_technical_actions() -> None:
    """Проверка согласования нескольких технических действий."""
    assert (
        humanize_experience_phrase(
            "Монтаж систем водоснабжения, обслуживание инженерных систем",
            grammatical_case="instrumental",
        )
        == "монтажом систем водоснабжения и обслуживанием инженерных систем"
    )
    assert (
        humanize_experience_phrase(
            "Монтаж систем водоснабжения, обслуживание инженерных систем",
        )
        == "монтажа систем водоснабжения и обслуживания инженерных систем"
    )


def test_humanize_experience_phrase_technical_actions_with_objects() -> None:
    """PR-33: Проверка морфологии технических действий с объектами."""
    assert (
        humanize_experience_phrase("Монтаж систем водоснабжения")
        == "монтажа систем водоснабжения"
    )
    assert (
        humanize_experience_phrase("Обслуживание сантехнического оборудования")
        == "обслуживания сантехнического оборудования"
    )
    assert (
        humanize_experience_phrase("Замена трубопроводов")
        == "замены трубопроводов"
    )
    assert (
        humanize_experience_phrase("Ремонт оборудования")
        == "ремонта оборудования"
    )
    assert (
        humanize_experience_phrase("Установка приборов")
        == "установки приборов"
    )
    assert (
        humanize_experience_phrase("Проведение инспекций")
        == "проведения инспекций"
    )
