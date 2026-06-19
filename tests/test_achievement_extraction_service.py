from app.services.achievement_extraction_service import AchievementExtractionService


def test_legacy_noisy_two_column_resume_layout_is_not_required_for_core_path() -> None:
    service = AchievementExtractionService(enable_legacy_recovery=False)

    drafts, warnings = service._build_achievement_drafts(
        """
СТАЖИРОВКИ
1. Создание ИИ-системы
для мониторинга безопасности в пансионатах для пожилых
"""
    )

    assert drafts
    assert drafts[0].fact_status == "needs_confirmation"
    assert drafts[0].ownership_confidence == "low"
    assert drafts[0].requires_confirmation is True
    assert warnings == [
        "normalized contribution signals were extracted; candidate ownership requires review"
    ]


def test_achievement_extraction_builds_generic_contribution_signals() -> None:
    service = AchievementExtractionService()

    signals = service._extract_normalized_contribution_signals(
        """
ДОСТИЖЕНИЯ
1. Reduced patient discharge delays by coordinating doctors, nurses and reception.
2. Negotiated supplier contracts and improved monthly purchasing control.
3. Prepared legal claim templates and standardized case documentation.
"""
    )

    assert [signal.title for signal in signals] == [
        "Reduced patient discharge delays by coordinating doctors, nurses and reception.",
        "Negotiated supplier contracts and improved monthly purchasing control.",
        "Prepared legal claim templates and standardized case documentation.",
    ]
    assert all(signal.source_layer == "generic_extraction" for signal in signals)
    assert all(signal.ownership_confidence == "low" for signal in signals)
    assert all(signal.requires_confirmation is True for signal in signals)
    assert all(signal.contribution_type in {"achievement", "operational_contribution"} for signal in signals)


def test_achievement_extraction_handles_empty_or_non_document_input() -> None:
    service = AchievementExtractionService()

    drafts, warnings = service._build_achievement_drafts("")

    assert drafts == []
    assert warnings == ["no contribution signals detected confidently"]


def test_private_noisy_recovery_is_legacy_and_not_generic_default() -> None:
    service = AchievementExtractionService()

    assert service.legacy_private_recovery_marker == "legacy_candidate_specific_heuristic"

    signals = service._extract_normalized_contribution_signals(
        """
СТАЖИРОВКИ
1. Создание ИИ-системы
для мониторинга безопасности в пансионатах для пожилых
"""
    )

    assert signals[0].source_layer == "generic_extraction"


def test_achievement_extraction_legacy_recovery_can_be_disabled() -> None:
    service = AchievementExtractionService(enable_legacy_recovery=False)

    assert service._recover_private_noisy_ai_achievement_title_legacy(
        [
            "Создание ИИ-системы",
            "для мониторинга безопасности в пансионатах для пожилых",
        ]
    ) is None


def test_extract_contribution_signals_for_review_returns_signals_and_review_warning() -> None:
    service = AchievementExtractionService()

    signals, warnings = service.extract_contribution_signals_for_review(
        """
ACHIEVEMENTS
- Coordinated legal document review and reduced turnaround time.
- Improved warehouse shift handover process.
"""
    )

    assert [signal.title for signal in signals] == [
        "Coordinated legal document review and reduced turnaround time.",
        "Improved warehouse shift handover process.",
    ]
    assert all(signal.ownership_confidence == "low" for signal in signals)
    assert all(signal.requires_confirmation is True for signal in signals)
    assert warnings == [
        "normalized contribution signals were extracted; candidate ownership requires review"
    ]


def test_splits_inline_dash_separated_achievements() -> None:
    service = AchievementExtractionService()

    result, warnings = service.extract_contribution_signals_for_review(
        """
        Достижения:
        - Снизил количество ошибок комплектации на 30% - Сократил время обработки заказов
        - Организовал обучение новых сотрудников
        """
    )

    titles = [item.title for item in result]

    assert "Снизил количество ошибок комплектации на 30%" in titles
    assert "Сократил время обработки заказов" in titles
    assert "Организовал обучение новых сотрудников" in titles


def test_skips_numeric_noise_contribution_title() -> None:
    service = AchievementExtractionService()

    signals, _ = service.extract_contribution_signals_for_review(
        """
        Достижения:
        - 1
        - Сократила количество ошибок в первичных документах
        """
    )

    titles = [item.title for item in signals]

    assert "1" not in titles
    assert "Сократила количество ошибок в первичных документах" in titles


def test_splits_multiple_dash_separated_achievements() -> None:
    service = AchievementExtractionService()

    signals, _ = service.extract_contribution_signals_for_review(
        """
        Достижения:
        - Запустила 8 проектов в срок - Снизила количество просроченных задач на 40% - Внедрила систему проектной отчётности
        """
    )

    titles = [item.title for item in signals]

    assert "Запустила 8 проектов в срок" in titles
    assert "Снизила количество просроченных задач на 40%" in titles
    assert "Внедрила систему проектной отчётности" in titles


def test_achievement_extraction_splits_designer_inline_participation_result() -> None:
    service = AchievementExtractionService()

    signals, warnings = service.extract_contribution_signals_for_review(
        """
        Достижения:
        Подготовила более 200 рекламных материалов для федеральных кампаний Участвовала в ребрендинге продуктовой линейки
        """
    )

    titles = [item.title for item in signals]

    assert titles == [
        "Подготовила более 200 рекламных материалов для федеральных кампаний",
        "Участвовала в ребрендинге продуктовой линейки",
    ]
    assert warnings == [
        "normalized contribution signals were extracted; candidate ownership requires review"
    ]


def test_achievement_extraction_ignores_pdf_bullet_layout_noise() -> None:
    service = AchievementExtractionService()

    signals, warnings = service.extract_contribution_signals_for_review(
        """
Марина Соколова Бухгалтер Опыт: ООО «РегионТрейд» Бухгалтер 2020–2026 Обязанности:
Ведение первичной бухгалтерской документации Работа с актами, счетами, накладными и счетами-фактурами
Сверка взаиморасчётов с контрагентами Подготовка платежных поручений Работа в 1С:Бухгалтерия и Excel
Участие в подготовке данных для налоговой и бухгалтерской отчётности Достижения:
Сократила количество ошибок в первичных документах Навела порядок в архиве закрывающих документов
Ускорила процесс сверки с контрагентами Подготовила шаблоны для регулярных бухгалтерских операций
Навыки: 1С:Бухгалтерия Первичная документация Сверка взаиморасчётов Банк-клиент Excel НДС
Акты сверки Деловая переписка Образование: Финансовый колледж Бухгалтерский учёт и экономика
• • • • • • • • • • 1
"""
    )

    titles = [item.title for item in signals]

    assert "1" not in titles
    assert signals
    assert any("Сократила количество ошибок" in title for title in titles)
    assert warnings == [
        "normalized contribution signals were extracted; candidate ownership requires review"
    ]


def test_achievement_extraction_strips_inline_skills_heading_tail() -> None:
    service = AchievementExtractionService()

    signals, warnings = service.extract_contribution_signals_for_review(
        """
Достижения:
- Провёл более 5000 консультаций Навыки:
Терапия Медицинская документация
"""
    )

    assert [signal.title for signal in signals] == [
        "Провёл более 5000 консультаций"
    ]
    assert warnings == [
        "normalized contribution signals were extracted; candidate ownership requires review"
    ]


def test_strip_inline_layout_heading_tail_handles_terminal_heading() -> None:
    service = AchievementExtractionService()

    cleaned = service._strip_inline_layout_heading_tail(
        "Провёл более 5000 консультаций Навыки:"
    )

    assert cleaned == "Провёл более 5000 консультаций"


def test_achievement_extraction_strips_inline_skills_heading_after_title_cleaning() -> None:
    service = AchievementExtractionService()

    signals = service._extract_normalized_contribution_signals(
        """
Достижения:
Провёл более 5000 консультаций Навыки:
Терапия Медицинская документация
"""
    )

    assert [signal.title for signal in signals] == [
        "Провёл более 5000 консультаций"
    ]
    assert all("Навыки" not in signal.source_text for signal in signals)


def test_real_doctor_achievement_does_not_keep_inline_skills_heading() -> None:
    service = AchievementExtractionService()

    drafts, warnings = service._build_achievement_drafts(
        """
Достижения:
- Сократил среднее время ожидания приёма - Участвовал во внедрении электронной медкарты
- Провёл более 5000 консультаций Навыки:
Терапия Медицинская документация
"""
    )

    assert [draft.title for draft in drafts] == [
        "Сократил среднее время ожидания приёма - Участвовал во внедрении электронной медкарты",
        "Провёл более 5000 консультаций",
    ]


def test_achievement_extraction_skips_medical_responsibilities_before_achievements() -> None:
    service = AchievementExtractionService()

    drafts, warnings = service._build_achievement_drafts(
        """
ОПЫТ РАБОТЫ
- Диагностика пациентов
- Назначение лечения

КЛЮЧЕВЫЕ ДОСТИЖЕНИЯ
- Сократил время ожидания приёма
- Провёл более 5000 консультаций
"""
    )

    assert [draft.title for draft in drafts] == [
        "Сократил время ожидания приёма",
        "Провёл более 5000 консультаций",
    ]
    assert all("Диагностика пациентов" not in draft.title for draft in drafts)
    assert all("Назначение лечения" not in draft.title for draft in drafts)
    assert warnings == [
        "normalized contribution signals were extracted; candidate ownership requires review"
    ]


def test_achievement_extraction_skips_generic_responsibilities_before_achievements() -> None:
    service = AchievementExtractionService()

    drafts, warnings = service._build_achievement_drafts(
        """
ОПЫТ РАБОТЫ
- Поддержка клиентов
- Координация команды
- Ведение документации

ДОСТИЖЕНИЯ
- Сократил время ответа на запросы
- Внедрил шаблоны для повторяющихся задач
"""
    )

    assert [draft.title for draft in drafts] == [
        "Сократил время ответа на запросы",
        "Внедрил шаблоны для повторяющихся задач",
    ]
    assert all("Поддержка клиентов" not in draft.title for draft in drafts)
    assert all("Координация команды" not in draft.title for draft in drafts)
    assert all("Ведение документации" not in draft.title for draft in drafts)
    assert warnings == [
        "normalized contribution signals were extracted; candidate ownership requires review"
    ]


def test_achievement_extraction_does_not_attach_next_company_to_achievement() -> None:
    service = AchievementExtractionService()

    drafts, warnings = service._build_achievement_drafts(
        """
Достижения:
1. Разработал чек-лист профилактического обслуживания оборудования
МУП «Горводоканал»
Слесарь-сантехник
09.2022 — настоящее время
Обязанности:
- Ремонт трубопроводов и запорной арматуры
"""
    )

    assert [draft.title for draft in drafts] == [
        "Разработал чек-лист профилактического обслуживания оборудования"
    ]
    assert all("Горводоканал" not in draft.title for draft in drafts)
    assert warnings == [
        "normalized contribution signals were extracted; candidate ownership requires review"
    ]


def test_achievement_extraction_strips_inline_company_tail_from_title() -> None:
    service = AchievementExtractionService()

    drafts, warnings = service._build_achievement_drafts(
        """
Достижения:
- Разработал чек-лист профилактического обслуживания оборудования МУП «Горводоканал»
Слесарь-сантехник
"""
    )

    assert [draft.title for draft in drafts] == [
        "Разработал чек-лист профилактического обслуживания оборудования"
    ]
    assert all("Горводоканал" not in draft.title for draft in drafts)
    assert warnings == [
        "normalized contribution signals were extracted; candidate ownership requires review"
    ]


def test_generic_contribution_extraction_does_not_depend_on_legacy_recovery() -> None:
    service = AchievementExtractionService(enable_legacy_recovery=False)

    signals, warnings = service.extract_contribution_signals_for_review(
        """
PROJECTS
1. Created AI monitoring workflow for care home safety.
2. Automated image review for product quality control.
"""
    )

    assert [signal.title for signal in signals] == [
        "Created AI monitoring workflow for care home safety.",
        "Automated image review for product quality control.",
    ]
    assert all(signal.source_layer == "generic_extraction" for signal in signals)
    assert warnings == [
        "normalized contribution signals were extracted; candidate ownership requires review"
    ]


def test_core_achievement_extraction_has_legacy_recovery_disabled_path() -> None:
    service = AchievementExtractionService(enable_legacy_recovery=False)

    drafts, warnings = service._build_achievement_drafts(
        """
ACHIEVEMENTS
1. Coordinated cross-functional rollout and improved response time.
2. Prepared compliance checklist and reduced review rework.
"""
    )

    assert [draft.title for draft in drafts] == [
        "Coordinated cross-functional rollout and improved response time.",
        "Prepared compliance checklist and reduced review rework.",
    ]
    assert all(draft.ownership_confidence == "low" for draft in drafts)
    assert all(draft.requires_confirmation is True for draft in drafts)
    assert warnings == [
        "normalized contribution signals were extracted; candidate ownership requires review"
    ]


def test_achievement_extraction_legacy_resume_layout_noise_can_be_disabled() -> None:
    service = AchievementExtractionService(enable_legacy_recovery=False)

    assert service._looks_like_resume_layout_noise("АЛТАЙСКИЙ ГОСУДАРСТВЕННЫЙ") is False
