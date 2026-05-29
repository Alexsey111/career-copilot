from app.services.achievement_extraction_service import AchievementExtractionService


# Legacy regression: this protects compatibility with an old noisy private PDF layout.
# It must not define generic extraction behavior.
def test_legacy_noisy_two_column_resume_layout_still_supported() -> None:
    service = AchievementExtractionService(enable_legacy_recovery=True)

    drafts, warnings = service._build_achievement_drafts(
        """
г.Барнаул, Россия, 656060
ул. Антона Петрова, д.262, кв. 306
(+7) 9039115133
lev.21.06.2005@gmail.com
https://github.com/Alexsey111
Перминов Алексей
30.11.1972 г.р.
Профессиональные навыки
Python, Git, Искусственный интеллект, LLM, Нейросети Прошел 3 стажировки по (промптинг), Создание нейроассистентов, Чат-боты, API, SQL,
Анализ данных, Tensorflow, Vibe-coding.
направлению Data Science:
1. Создание ИИ-системы
Желаемая должность
для мониторинга безопасности в Prompt Engineering, Data Science, Vibe-coding пансионатах для
пожилых
ОПЫТ РАБОТЫ
(ООО «СГЦ ОПЕКА»)
2. Автоматизированный Алтайский Государственный Медицинский ИИ-контроль качества Университет, электромонтер по ремонту и
ПВХ оконных изделий обслуживанию электрооборудования по изображениям и
01.01.2015 - по настоящее время
видео (ООО «ТД «Проплекс»)
3. «ИИ-анализ текстовых
ОБРАЗОВАНИЕ
отзывов населения о социальных объектах инфраструктуры для Алтайский государственный технический
прогнозирования университет имени И.И. Ползунова, Барнаул развития городской среды и оценки
инженер, Автомобиле- и тракторостроение устойчивого развития 1999 - 2001 территорий (Московский
Политехнический Университет)»
Курсы
Data Science, нейронные сети, машинное обучение и
искусственный интеллект
"""
    )

    assert len(drafts) == 3
    assert all("Алтайский Государственный Медицинский" not in draft.title for draft in drafts)
    assert all("электромонтер" not in draft.title.lower() for draft in drafts)

    assert all(draft.fact_status == "needs_confirmation" for draft in drafts)
    assert all(draft.ownership_confidence == "low" for draft in drafts)
    assert all(draft.requires_confirmation is True for draft in drafts)
    assert warnings == [
        "normalized contribution signals were extracted; candidate ownership requires review"
    ]


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
