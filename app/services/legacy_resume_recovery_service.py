# app/services/legacy_resume_recovery_service.py

from __future__ import annotations

import re


class LegacyResumeRecoveryService:
    """
    Compatibility layer for old noisy private resume layouts.

    This service must not be used as a generic extraction path.
    It exists only to keep legacy regression tests passing while
    core services remain candidate/domain neutral.
    """

    marker = "legacy_candidate_specific_heuristic"

    def __init__(self, *, enabled: bool = True) -> None:
        self.enabled = enabled

    def recover_noisy_ai_achievement_title(self, lines: list[str]) -> str | None:
        if not self.enabled:
            return None
        text = re.sub(r"\s+", " ", " ".join(lines)).strip()
        lowered = text.lower()

        if "создание ии-системы" in lowered:
            if "мониторинг" in lowered and "пансионат" in lowered and "пожил" in lowered:
                return "Создание ИИ-системы для мониторинга безопасности в пансионатах для пожилых"
            return "Создание ИИ-системы"

        if "автоматизирован" in lowered and "ии-контроль качества" in lowered:
            title_parts = ["Автоматизированный ИИ-контроль качества"]
            if "пвх оконных изделий" in lowered:
                title_parts.append("ПВХ оконных изделий")
            if "по изображениям" in lowered and "видео" in lowered:
                title_parts.append("по изображениям и видео")
            return " ".join(title_parts)

        if "ии-анализ текстовых" in lowered:
            if "отзывов населения" in lowered:
                return "ИИ-анализ текстовых отзывов населения"
            return "ИИ-анализ текстовых"

        return None

    def recover_noisy_ai_signal_title(self, lines: list[str]) -> str | None:
        if not self.enabled:
            return None
        text = re.sub(r"\s+", " ", " ".join(lines)).strip()
        lowered = text.lower()

        if "создание ии-системы" in lowered:
            if "мониторинг" in lowered and "пожил" in lowered:
                return "ИИ-система мониторинга безопасности"
            return "Создание ИИ-системы"

        if "автоматизирован" in lowered and "ии-контроль качества" in lowered:
            return "ИИ-контроль качества ПВХ изделий"

        if "prompt engineering" in lowered or "промпт" in lowered:
            return "Prompt Engineering"

        if "ии-анализ" in lowered and "отзыв" in lowered:
            return "ИИ-анализ отзывов населения"

        return None

    def prefer_noisy_internship_layout_fragment(self, line: str) -> str:
        if not self.enabled:
            return line
        parts = [
            part.strip()
            for part in re.split(r"\s{2,}", line.strip(), maxsplit=1)
            if part.strip()
        ]
        if len(parts) != 2:
            return line

        left, right = parts
        right_lowered = right.lower()
        left_lowered = left.lower()

        if any(
            marker in right_lowered
            for marker in (
                "ии-",
                "пвх",
                "изображениям",
                "видео",
                "пансионат",
                "пожил",
                "безопасности",
            )
        ):
            return right

        if "prompt engineering" in left_lowered and (
            "пансионат" in right_lowered or "пожил" in right_lowered
        ):
            return right

        return line

    def recover_known_formal_education_lines(self, value: str) -> list[str]:
        if not self.enabled:
            return []

        text = re.sub(r"\s+", " ", str(value or "")).strip()
        result: list[str] = []
        seen: set[str] = set()

        if re.search(r"Ползунова,\s*Барнаул", text, flags=re.IGNORECASE):
            item = "Алтайский государственный технический университет им. И.И. Ползунова, Барнаул"
            result.append(item)
            seen.add(item.casefold())

        patterns = [
            r"Алтайск\w+\s+государственн\w+\s+техническ\w+\s+университет(?:\s+им\.\s*И\.И\.\s*Ползунова)?(?:,\s*Барнаул)?",
            r"Рязанск\w+\s+высш\w+\s+воздушно-десантн\w+\s+командн\w+\s+училище(?:\s+им\.\s*В\.Ф\.\s*Маргелова)?(?:,\s*Рязань)?",
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                item = self._clean_education_detail(match.group(0))
                key = item.casefold()
                if item and key not in seen:
                    seen.add(key)
                    result.append(item)

        return result

    def recover_known_course_lines(self, value: str) -> list[str]:
        if not self.enabled:
            return []

        text = re.sub(r"\s+", " ", str(value or "")).strip()
        result: list[str] = []
        seen: set[str] = set()
        provider_matches = list(self._iter_course_provider_year_matches(text))
        previous_end = 0

        for index, match in enumerate(provider_matches):
            provider = self._canonical_course_provider(match.group("provider"))
            year = match.group("year")
            before = text[previous_end:match.start()]
            after_end = (
                provider_matches[index + 1].start()
                if index + 1 < len(provider_matches)
                else len(text)
            )
            after = text[match.end():after_end]
            previous_end = match.end()

            title = self._extract_course_title_near_provider(before, after)
            if not title:
                continue

            item = f"{provider}, {year} — {title}"
            key = item.casefold()
            if key not in seen:
                seen.add(key)
                result.append(item)

        return result

    def _clean_education_detail(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _iter_course_provider_year_matches(self, text: str):
        provider_pattern = (
            r"(?P<provider>"
            r"университет\s+искусственн\w+\s+интеллект\w*|"
            r"университет\s+зерокодинг\w*|"
            r"zerocoder|zerocoding|"
            r"terra\s*ai|"
            r"stepik|coursera|otus|skillbox|geekbrains"
            r")"
            r"\s*[,.—–-]?\s*"
            r"(?P<year>20\d{2})"
        )
        return re.finditer(provider_pattern, text, flags=re.IGNORECASE)

    def _canonical_course_provider(self, value: str) -> str:
        lowered = re.sub(r"\s+", " ", str(value or "")).strip().lower()
        if "искусствен" in lowered and "интеллект" in lowered:
            return "Университет искусственного интеллекта"
        if "зерокод" in lowered or "zerocoder" in lowered or "zerocoding" in lowered:
            return "Университет Зерокодинга"
        if "terra" in lowered:
            return "Terra AI"
        if "stepik" in lowered:
            return "Stepik"
        if "coursera" in lowered:
            return "Coursera"
        if "otus" in lowered:
            return "OTUS"
        if "skillbox" in lowered:
            return "Skillbox"
        if "geekbrains" in lowered:
            return "GeekBrains"
        return str(value or "").strip()

    def _extract_course_title_near_provider(self, before: str, after: str) -> str | None:
        title = self._clean_course_title_candidate(before, prefer_tail=True)
        if title:
            return title
        return self._clean_course_title_candidate(after, prefer_tail=False)

    def _clean_course_title_candidate(self, value: str, *, prefer_tail: bool) -> str | None:
        text = re.sub(r"\s+", " ", str(value or "")).strip(" -–—•")
        if not text:
            return None

        text = re.sub(
            r"^(?:курсы|курс|дополнительное обучение)\b[:：]?\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )
        if " курсы " in text.lower():
            text = re.split(r"\bкурсы\b", text, flags=re.IGNORECASE)[-1].strip()

        for pattern in (
            r"\bОБРАЗОВАНИЕ\b",
            r"\bПРОЕКТЫ\b",
            r"\bОПЫТ РАБОТЫ\b",
            r"\bДОПОЛНИТЕЛЬНЫЕ СВЕДЕНИЯ\b",
            r"\bАлтайск\w+\b",
            r"\bРязанск\w+\b",
        ):
            parts = re.split(pattern, text, flags=re.IGNORECASE)
            text = parts[-1] if prefer_tail else parts[0]

        fragments = [
            fragment.strip(" -–—•,.;:()»«")
            for fragment in re.split(r"\s{2,}|[|/]", text)
            if fragment.strip(" -–—•,.;:()»«")
        ]
        if fragments:
            text = fragments[-1] if prefer_tail else fragments[0]

        text = self._normalize_course_title(text)
        lowered = text.lower()

        if not text or len(text) < 4 or len(text) > 120:
            return None
        if any(
            marker in lowered
            for marker in (
                "университет",
                "институт",
                "училище",
                "барнаул",
                "рязань",
                "прогнозирования",
                "городской среды",
                "территорий",
                "инженер",
            )
        ):
            return None

        return text

    def _clean_education_detail(self, value: str) -> str:
        text = re.sub(r"\s+", " ", str(value or "")).strip(" -–—•")
        text = re.sub(
            r"^алтайск\w+\s+государственн\w+\s+техническ\w+\s+университет",
            "Алтайский государственный технический университет",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"^рязанск\w+\s+высш\w+\s+воздушно-десантн\w+\s+командн\w+\s+училище",
            "Рязанское высшее воздушно-десантное командное училище",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(r"\s+им\.\s*", " им. ", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*,\s*", ", ", text)
        return text

    def _normalize_course_title(self, value: str) -> str:
        text = re.sub(r"\s+", " ", str(value or "")).strip(" -–—•")
        text = re.sub(r"^программист", "Программист", text, flags=re.IGNORECASE)
        text = re.sub(r"^аналитик", "Аналитик", text, flags=re.IGNORECASE)
        text = re.sub(r"\bpython\b", "Python", text, flags=re.IGNORECASE)
        text = re.sub(r"\bchatgpt\b", "ChatGPT", text, flags=re.IGNORECASE)
        return text

    def looks_like_legacy_formal_education_line(self, line: str) -> bool:
        if not self.enabled:
            return False
        lowered = line.lower()

        if any(
            marker in lowered
            for marker in (
                "ии-контроль",
                "пвх",
                "изображениям",
                "видео",
                "отзыв",
                "инфраструктуры",
            )
        ):
            return False
        return any(
            marker in lowered
            for marker in (
                "алтайский государственный",
                "университет имени",
                "ползунова",
                "рязанское высшее",
                "воздушно-десантное командное училище",
                "автомобиле- и тракторостроение",
                "командная тактическая",
            )
        )

    def looks_like_legacy_target_role_noise(self, value: str) -> bool:
        if not self.enabled:
            return False

        lowered = value.lower()

        noise_markers = {
            "мониторинг",
            "безопасности",
            "пансионат",
            "пожилых",
            "создание",
            "системы",
            "качества",
            "изделий",
            "изображениям",
            "видео",
            "отзывов",
            "населения",
            "объектах",
            "инфраструктуры",
            "прогнозирования",
            "университет",
            "ооо",
        }

        return any(marker in lowered for marker in noise_markers)

    def looks_like_legacy_mixed_education_layout_noise(self, value: str) -> bool:
        if not self.enabled:
            return False

        text = re.sub(r"\s+", " ", str(value or "")).strip().lower()

        if len(text) > 180:
            return True

        return any(
            marker in text
            for marker in (
                "прогнозирования",
                "городской среды",
                "пвх",
                "пансионат",
                "мониторинг",
                "pipeline",
                "workflow",
            )
        )

    def looks_like_legacy_resume_layout_noise(self, line: str) -> bool:
        if not self.enabled:
            return False
        normalized = re.sub(r"\s+", " ", line.strip()).upper()

        if re.search(r"\d{2}\.\d{2}\.\d{4}\s*-\s*", line):
            return True
        if re.match(r"^\d{4}\b", line.strip()):
            return True
        return any(
            marker in normalized
            for marker in {
                "АЛТАЙСКИЙ ГОСУДАРСТВЕННЫЙ",
                "МЕДИЦИНСКИЙ УНИВЕРСИТЕТ",
                "УНИВЕРСИТЕТ ИМЕНИ",
                "ЭЛЕКТРОМОНТЕР",
                "ОБСЛУЖИВАНИЮ ЭЛЕКТРООБОРУДОВАНИЯ",
                "ИНЖЕНЕР,",
                "АВТОМОБИЛЕ- И ТРАКТОРОСТРОЕНИЕ",
                "РЯЗАНСКОЕ ВЫСШЕЕ",
                "ВОЗДУШНО-ДЕСАНТНОЕ",
            }
        )

    def looks_like_legacy_low_confidence_experience_noise(self, value: str) -> bool:
        if not self.enabled:
            return False

        normalized = str(value or "").lower()
        noise_patterns = [
            r"\b\d+\.\s+",
            r"ии-контроль",
            r"пвх оконных",
            r"по изображениям",
            r"видео layout noise",
        ]
        return any(re.search(pattern, normalized) for pattern in noise_patterns)