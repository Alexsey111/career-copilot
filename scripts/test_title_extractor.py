from app.domain.vacancy_title_extractor import extract_vacancy_title

# Универсальные тесты для ЛЮБЫХ профессий
tests = [
    # "Мы ищем X"
    ("Мы ищем Python-разработчика, которому интересно не только писать код", "python"),
    ("Мы ищем бухгалтера с опытом работы от 3 лет", "бухгалтер"),
    ("Мы ищем юриста для работы с договорами", "юрист"),
    ("Мы ищем сантехника для обслуживания зданий", "сантехник"),
    # Простой заголовок
    ("Бухгалтер\nдо 70 000 ₽ за месяц", "бухгалтер"),
    ("Backend Developer\nОпыт: 2022-2026", "backend developer"),
    ("Графический дизайнер\nЦелевая должность", "дизайнер"),
    ("Заместитель директора по продажам", "заместитель директора"),
    # Заголовок в середине
    ("Уровень дохода не указан\nОпыт работы: 3-6 лет\nPython Developer", "python developer"),
    ("Опыт работы: 1-3 года\nСантехник\nПолная занятость", "сантехник"),
    # Английский
    ("We are looking for a Data Scientist with ML experience", "data scientist"),
    ("Hiring: Project Manager with 5+ years experience", "project manager"),
    # С приставкой
    ("Вакансия: Руководитель проектов", "руководитель проектов"),
    ("Позиция: Терапевт в клинику", "терапевт"),
]

passed = 0
failed = 0
for text, expected_keyword in tests:
    result = extract_vacancy_title(text, fallback="UNKNOWN")
    result_lower = result.lower()
    ok = expected_keyword.lower() in result_lower
    status = "OK" if ok else "FAIL"
    if ok:
        passed += 1
    else:
        failed += 1
    print(f"[{status}] '{text[:60]}...' -> '{result}' (keyword: '{expected_keyword}')")

print(f"\n{passed}/{passed+failed} passed")
