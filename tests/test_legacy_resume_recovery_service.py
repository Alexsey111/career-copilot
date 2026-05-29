from app.services.legacy_resume_recovery_service import LegacyResumeRecoveryService


def test_legacy_recovery_recovers_noisy_private_ai_achievement_title() -> None:
    service = LegacyResumeRecoveryService()

    title = service.recover_noisy_ai_achievement_title(
        [
            "Создание ИИ-системы",
            "для мониторинга безопасности в пансионатах для пожилых",
        ]
    )

    assert title == (
        "Создание ИИ-системы для мониторинга безопасности в пансионатах для пожилых"
    )
    assert service.marker == "legacy_candidate_specific_heuristic"


def test_legacy_recovery_recovers_noisy_profile_signal_title() -> None:
    service = LegacyResumeRecoveryService()

    title = service.recover_noisy_ai_signal_title(
        [
            "Автоматизированный ИИ-контроль качества",
            "ПВХ оконных изделий по изображениям и видео",
        ]
    )

    assert title == "ИИ-контроль качества ПВХ изделий"


def test_legacy_recovery_can_be_disabled() -> None:
    service = LegacyResumeRecoveryService(enabled=False)

    assert service.recover_noisy_ai_achievement_title(
        [
            "Создание ИИ-системы",
            "для мониторинга безопасности в пансионатах для пожилых",
        ]
    ) is None

    assert service.recover_noisy_ai_signal_title(
        [
            "Автоматизированный ИИ-контроль качества",
            "ПВХ оконных изделий по изображениям и видео",
        ]
    ) is None


def test_legacy_recovery_formal_education_lines() -> None:
    service = LegacyResumeRecoveryService()

    result = service.recover_known_formal_education_lines(
        "Алтайский государственный технический университет им. И.И. Ползунова, Барнаул"
    )

    assert any("Ползунова" in item for item in result)


def test_legacy_recovery_course_lines() -> None:
    service = LegacyResumeRecoveryService()

    result = service.recover_known_course_lines(
        "Stepik, 2023 Python course"
    )

    assert any("Python" in item or "Stepik" in item for item in result)


def test_legacy_recovery_recovers_known_formal_education_lines() -> None:
    service = LegacyResumeRecoveryService()

    items = service.recover_known_formal_education_lines(
        "Алтайский государственный технический университет имени И.И. Ползунова, Барнаул"
    )

    assert any("Ползунова" in item for item in items)


def test_legacy_recovery_recovers_known_course_lines() -> None:
    service = LegacyResumeRecoveryService()

    items = service.recover_known_course_lines(
        "Курсы Python с нуля Университет Зерокодинга 2024"
    )

    assert items == [
        "Университет Зерокодинга, 2024 — Python с нуля"
    ]


def test_legacy_education_and_course_recovery_can_be_disabled() -> None:
    service = LegacyResumeRecoveryService(enabled=False)

    assert service.recover_known_formal_education_lines(
        "Алтайский государственный технический университет имени И.И. Ползунова, Барнаул"
    ) == []

    assert service.recover_known_course_lines(
        "Курсы Python с нуля Университет Зерокодинга 2024"
    ) == []


def test_legacy_prefer_noisy_internship_layout_fragment() -> None:
    service = LegacyResumeRecoveryService()

    assert service.prefer_noisy_internship_layout_fragment(
        "Python с нуля    ИИ-контроль качества ПВХ изделий"
    ) == "ИИ-контроль качества ПВХ изделий"

    assert service.prefer_noisy_internship_layout_fragment(
        "Prompt Engineering    для пансионатов для пожилых"
    ) == "для пансионатов для пожилых"


def test_legacy_prefer_noisy_internship_layout_fragment_disabled() -> None:
    service = LegacyResumeRecoveryService(enabled=False)

    assert (
        service.prefer_noisy_internship_layout_fragment(
            "Python с нуля    ИИ-контроль качества ПВХ изделий"
        )
        == "Python с нуля    ИИ-контроль качества ПВХ изделий"
    )


def test_legacy_recovery_prefers_noisy_internship_right_column_fragment() -> None:
    service = LegacyResumeRecoveryService()

    line = (
        "Автоматизированный Алтайский Государственный Медицинский  "
        "ИИ-контроль качества ПВХ оконных изделий"
    )

    assert service.prefer_noisy_internship_layout_fragment(line) == (
        "ИИ-контроль качества ПВХ оконных изделий"
    )


def test_legacy_internship_layout_fragment_recovery_can_be_disabled() -> None:
    service = LegacyResumeRecoveryService(enabled=False)

    line = (
        "Автоматизированный Алтайский Государственный Медицинский  "
        "ИИ-контроль качества ПВХ оконных изделий"
    )

    assert service.prefer_noisy_internship_layout_fragment(line) == line


def test_legacy_recovery_looks_like_formal_education_line() -> None:
    service = LegacyResumeRecoveryService()

    assert service.looks_like_legacy_formal_education_line(
        "Алтайский государственный технический университет имени И.И. Ползунова"
    ) is True

    assert service.looks_like_legacy_formal_education_line(
        "ИИ-контроль качества ПВХ оконных изделий по изображениям и видео"
    ) is False


def test_legacy_looks_like_formal_education_line_can_be_disabled() -> None:
    service = LegacyResumeRecoveryService(enabled=False)

    assert service.looks_like_legacy_formal_education_line(
        "Алтайский государственный технический университет имени И.И. Ползунова"
    ) is False


def test_legacy_recovery_detects_formal_education_line() -> None:
    service = LegacyResumeRecoveryService()

    assert service.looks_like_legacy_formal_education_line(
        "Алтайский государственный технический университет имени И.И. Ползунова"
    ) is True

    assert service.looks_like_legacy_formal_education_line(
        "ИИ-контроль качества ПВХ оконных изделий по изображениям и видео"
    ) is False


def test_legacy_formal_education_line_detection_can_be_disabled() -> None:
    service = LegacyResumeRecoveryService(enabled=False)

    assert service.looks_like_legacy_formal_education_line(
        "Алтайский государственный технический университет имени И.И. Ползунова"
    ) is False


def test_legacy_recovery_detects_resume_layout_noise() -> None:
    service = LegacyResumeRecoveryService()

    assert service.looks_like_legacy_resume_layout_noise(
        "Алтайский Государственный Медицинский Университет"
    ) is True
    assert service.looks_like_legacy_resume_layout_noise(
        "01.01.2015 - по настоящее время"
    ) is True
    assert service.looks_like_legacy_resume_layout_noise(
        "Managed clinic operations and improved patient flow"
    ) is False


def test_legacy_resume_layout_noise_detection_can_be_disabled() -> None:
    service = LegacyResumeRecoveryService(enabled=False)

    assert service.looks_like_legacy_resume_layout_noise(
        "Алтайский Государственный Медицинский Университет"
    ) is False


def test_legacy_recovery_detects_target_role_noise() -> None:
    service = LegacyResumeRecoveryService()

    assert service.looks_like_legacy_target_role_noise(
        "для мониторинга безопасности в пансионатах для пожилых"
    ) is True

    assert service.looks_like_legacy_target_role_noise(
        "Product Manager"
    ) is False


def test_legacy_target_role_noise_detection_can_be_disabled() -> None:
    service = LegacyResumeRecoveryService(enabled=False)

    assert service.looks_like_legacy_target_role_noise(
        "для мониторинга безопасности в пансионатах для пожилых"
    ) is False


def test_legacy_recovery_detects_mixed_education_layout_noise() -> None:
    service = LegacyResumeRecoveryService()

    assert service.looks_like_legacy_mixed_education_layout_noise(
        "прогнозирования развития городской среды и оценки устойчивого развития"
    ) is True

    assert service.looks_like_legacy_mixed_education_layout_noise(
        "Московский государственный университет, юридический факультет"
    ) is False


def test_legacy_mixed_education_layout_noise_detection_can_be_disabled() -> None:
    service = LegacyResumeRecoveryService(enabled=False)

    assert service.looks_like_legacy_mixed_education_layout_noise(
        "прогнозирования развития городской среды"
    ) is False


def test_legacy_recovery_detects_low_confidence_experience_noise() -> None:
    service = LegacyResumeRecoveryService()

    assert service.looks_like_legacy_low_confidence_experience_noise(
        "ИИ-контроль качества ПВХ оконных изделий по изображениям"
    ) is True

    assert service.looks_like_legacy_low_confidence_experience_noise(
        "Clinic Operations Manager"
    ) is False


def test_legacy_low_confidence_experience_noise_can_be_disabled() -> None:
    service = LegacyResumeRecoveryService(enabled=False)

    assert service.looks_like_legacy_low_confidence_experience_noise(
        "ИИ-контроль качества ПВХ оконных изделий по изображениям"
    ) is False