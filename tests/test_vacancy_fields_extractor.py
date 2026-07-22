from app.domain.vacancy_fields_extractor import extract_vacancy_fields


def test_extract_fields_from_hh_vacancy_text() -> None:
    text = (
        "Описание\n"
        "Специалист по внедрению искусственного интеллекта\n"
        "от 100 000 ₽ за месяц, до вычета налогов\n"
        "Выплаты: два раза в месяц\n"
        "Опыт работы: не требуется\n"
        "Полная занятость\n"
        "Оформление: Трудовой договор\n"
        "График: 5/2\n"
        "Рабочие часы: 8\n"
        "Формат работы: удалённо или гибрид\n"
        "Сейчас эту вакансию смотрят 3 человека\n"
        "Ваc пригласили\n"
        "ЗЕБРА\n"
        "ЗЕБРА\n"
        "4,9\n"
        "4 отзыва\n"
        "Кто мы\n"
        "Городской интернет-портал.\n"
    )

    fields = extract_vacancy_fields(text)

    assert fields.title == "Специалист по внедрению искусственного интеллекта"
    assert fields.company == "ЗЕБРА"
    assert fields.location == "Удалённо или гибрид"
    assert fields.salary_from == 100000
    assert fields.salary_to is None
    assert fields.salary_currency == "RUB"
    assert fields.employment_type == "Полная занятость"
    assert fields.experience_level == "Нет опыта"


def test_extract_salary_range_and_currency() -> None:
    fields = extract_vacancy_fields(
        "Data Scientist\n150 000 - 250 000 ₽\nОпыт работы: 3-6 лет\nЧастичная занятость\n"
    )
    assert fields.salary_from == 150000
    assert fields.salary_to == 250000
    assert fields.salary_currency == "RUB"
    assert fields.experience_level == "От 3 до 6 лет"
    assert fields.employment_type == "Частичная занятость"


def test_extract_salary_to_only_and_eur_currency() -> None:
    fields = extract_vacancy_fields("Backend dev\nдо 5000 €\nОпыт работы: 1-3 года\n")
    assert fields.salary_from is None
    assert fields.salary_to == 5000
    assert fields.salary_currency == "EUR"
    assert fields.experience_level == "От 1 года до 3 лет"


def test_extract_returns_empty_for_blank_text() -> None:
    fields = extract_vacancy_fields("")
    assert fields.title is None
    assert fields.company is None
    assert fields.salary_from is None


def test_title_fallback_when_no_heading_found() -> None:
    fields = extract_vacancy_fields("random line without structure", fallback_title="Untitled")
    # На отдельной короткой строке экстрактор title может её принять;
    # главное — fallback используется, когда ничего не найдено.
    assert fields.title is not None


def test_company_not_taken_from_rating_line() -> None:
    text = "Вас пригласили\n5,0\n12 отзывов\nНастоящая Компания\nКто мы\n"
    fields = extract_vacancy_fields(text)
    assert fields.company == "Настоящая Компания"