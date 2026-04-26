from app.services.resume_parser_service import ResumeParserService


def test_repair_common_mojibake_restores_utf8_text() -> None:
    service = ResumeParserService()
    original = "\u041f\u0435\u0440\u043c\u0438\u043d\u043e\u0432"
    mojibake = original.encode("utf-8").decode("latin1")

    repaired = service._repair_common_mojibake(mojibake)

    assert repaired == original
    assert service._text_quality_score(repaired) > service._text_quality_score(mojibake)


def test_normalize_text_keeps_dates_contacts_and_following_content_separate() -> None:
    service = ResumeParserService()

    raw_text = """
ОБРАЗОВАНИЕ
Алтайский государственный технический университет имени И.И. Ползунова, Барнаул инженер, Автомобиле- и тракторостроение
1999 - 2001
г.Барнаул, Россия, 656060
ул. Антона Петрова, д.262, кв. 306
(+7) 9039115133
lev.21.06.2005@gmail.com
https://github.com/Alexsey111
Прошел 3 стажировки по направлению Data Science:
1. Создание ИИ-системы для мониторинга безопасности
"""

    normalized = service._normalize_text(raw_text)
    lines = normalized.splitlines()

    assert "1999 - 2001" in lines
    assert "г.Барнаул, Россия, 656060" in lines
    assert "ул. Антона Петрова, д.262, кв. 306" in lines
    assert "(+7) 9039115133" in lines
    assert "lev.21.06.2005@gmail.com" in lines
    assert "https://github.com/Alexsey111" in lines
    assert "Прошел 3 стажировки по направлению Data Science:" in lines

    assert "1999 - 2001 г.Барнаул" not in normalized
    assert "656060 ул. Антона Петрова" not in normalized
    assert "(+7) 9039115133 lev.21.06.2005@gmail.com" not in normalized
    assert "https://github.com/Alexsey111 Прошел 3 стажировки" not in normalized


def test_normalize_text_still_merges_short_broken_plain_lines() -> None:
    service = ResumeParserService()

    raw_text = """
Создание AI-системы мониторинга
безопасности в пансионатах
для пожилых
"""

    normalized = service._normalize_text(raw_text)

    assert normalized == (
        "Создание AI-системы мониторинга безопасности в пансионатах для пожилых"
    )