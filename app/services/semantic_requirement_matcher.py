# app\services\semantic_requirement_matcher.py

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class SemanticMatchResult:
    matched: bool
    confidence: float
    matched_term: str | None
    reason: str


class SemanticRequirementMatcher:
    def match(
        self,
        requirement: str,
        candidate_terms: list[str],
    ) -> SemanticMatchResult:
        requirement_norm = self._normalize(requirement)
        terms = [term for term in candidate_terms if str(term or "").strip()]
        normalized_terms = [(term, self._normalize(term)) for term in terms]

        if not requirement_norm or not normalized_terms:
            return SemanticMatchResult(False, 0.0, None, "empty_input")

        for original, normalized in normalized_terms:
            if requirement_norm == normalized:
                return SemanticMatchResult(True, 1.0, original, "exact_match")

        for original, normalized in normalized_terms:
            if requirement_norm in normalized or normalized in requirement_norm:
                return SemanticMatchResult(True, 0.9, original, "substring_match")

        requirement_aliases = self._aliases_for(requirement_norm)
        for original, normalized in normalized_terms:
            # 1. alias содержится внутри evidence
            for alias in requirement_aliases:
                if alias and alias in normalized:
                    return SemanticMatchResult(
                        True,
                        0.85,
                        original,
                        "semantic_alias_contains_match",
                    )

            # 2. evidence принадлежит alias-кластеру
            term_aliases = self._aliases_for(normalized)
            if requirement_aliases & term_aliases:
                return SemanticMatchResult(
                    True,
                    0.80,
                    original,
                    "shared_semantic_alias_cluster",
                )

        requirement_tokens = self._stem_tokens(requirement_norm)
        for original, normalized in normalized_terms:
            term_tokens = self._stem_tokens(normalized)
            if not requirement_tokens or not term_tokens:
                continue

            overlap = requirement_tokens & term_tokens
            overlap_ratio = len(overlap) / max(len(requirement_tokens), 1)

            if len(overlap) >= 2 and overlap_ratio >= 0.4:
                return SemanticMatchResult(True, 0.7, original, "token_stem_overlap")

            if len(overlap) >= 1 and self._is_short_requirement(requirement_norm):
                return SemanticMatchResult(True, 0.6, original, "short_requirement_token_overlap")

        return SemanticMatchResult(False, 0.0, None, "no_semantic_match")

    def _normalize(self, value: str) -> str:
        text = str(value or "").casefold()
        text = text.replace("ё", "е")
        text = text.replace("1c", "1с")
        text = re.sub(r"[^\wа-яА-ЯёЁ+#./-]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        text = (
            text
            .replace("электронной медкарты", "электронная медицинская карта")
            .replace("электронную медкарту", "электронная медицинская карта")
            .replace("электронные медкарты", "электронная медицинская карта")
            .replace("консультаций", "консультации")
            .replace("консультациям", "консультации")
            .replace("консультировал", "консультации")
            .replace("консультирование", "консультации")
        )

        replacements = {
            "эмк": "электронная медицинская карта",
            "мис": "медицинская информационная система",
            "пк": "персональный компьютер",
            "api": "api",
            "rest api": "rest api",
            "corel draw": "coreldraw",
            "corel": "coreldraw",
        }
        return replacements.get(text, text)

    def _aliases_for(self, normalized_value: str) -> set[str]:
        aliases: dict[str, set[str]] = {
            "пользователь персональный компьютер": {
                "персональный компьютер",
                "электронная медицинская карта",
                "электронной медкарты",
                "электронные медицинские системы",
                "медицинская информационная система",
                "ведение медицинской документации",
                "электронная медкарта",
                "эмк",
                "мис",
                "excel",
                "word",
                "офисные программы",
            },
            "пользователь пк": {
                "персональный компьютер",
                "электронная медицинская карта",
                "электронной медкарты",
                "электронные медицинские системы",
                "медицинская информационная система",
                "ведение медицинской документации",
                "электронная медкарта",
                "эмк",
                "мис",
                "excel",
                "word",
                "офисные программы",
            },
            "персональный компьютер": {
                "пользователь персональный компьютер",
                "пользователь пк",
                "электронная медицинская карта",
                "электронной медкарты",
                "электронные медицинские системы",
                "медицинская информационная система",
                "ведение медицинской документации",
                "excel",
                "word",
            },
            "коммуникация": {
                "консультации",
                "консультаций",
                "консультирование",
                "прием пациентов",
                "прием клиентов",
                "маршрутизация пациентов",
                "деловая переписка",
                "ведение переговоров",
                "работа с клиентами",
                "работа с пациентами",
            },
            "ответственность": {
                "самостоятельное ведение",
                "координация",
                "организация работы",
                "доведение задач до результата",
                "руководство",
                "управление",
            },
            "rest api": {
                "fastapi",
                "api",
                "backend api",
                "разработка api",
                "интеграция api",
            },
            "api": {
                "fastapi",
                "rest api",
                "backend api",
                "разработка api",
                "интеграция api",
            },
            "договорное право": {
                "договоры",
                "договорная работа",
                "подготовка договоров",
                "сопровождение договоров",
                "контроль исполнения договоров",
            },
            "документооборот": {
                "ведение документации",
                "медицинская документация",
                "первичная документация",
                "договоры",
                "акты",
                "отчетность",
            },
            "бухгалтерия": {
                "1с бухгалтерия",
                "первичная документация",
                "акты сверки",
                "ндс",
                "банк клиент",
                "сверка взаиморасчетов",
            },
            "складская логистика": {
                "wms",
                "склад",
                "складские процессы",
                "контроль остатков",
                "приемка товара",
                "отгрузка товара",
            },
            "графические редакторы": {
                "adobe photoshop",
                "adobe illustrator",
                "figma",
                "coreldraw",
            },
            "терапия": {
                "врач терапевт",
                "амбулаторный прием",
                "диагностика пациентов",
                "назначение лечения",
                "клиническая диагностика",
            },
            "медицинская документация": {
                "ведение медицинской документации",
                "электронная медицинская карта",
                "электронные медицинские системы",
                "отчетность",
            },
        }

        normalized_aliases: set[str] = set()
        for key, values in aliases.items():
            key_norm = self._normalize(key)
            value_norms = {self._normalize(item) for item in values}
            cluster = {key_norm, *value_norms}

            if normalized_value in cluster:
                normalized_aliases |= cluster

        return normalized_aliases

    def _stem_tokens(self, value: str) -> set[str]:
        stopwords = {
            "и", "или", "в", "во", "на", "по", "для", "с", "со", "от", "до",
            "при", "об", "из", "за", "работа", "работы", "опыт", "наличие",
            "знание", "умение", "готовность", "пользователь",
        }
        return {
            self._stem(token)
            for token in re.findall(r"[a-zа-яё0-9+#./-]+", value.casefold())
            if token not in stopwords and len(token) >= 3
        }

    def _stem(self, token: str) -> str:
        text = str(token or "").strip().casefold().replace("ё", "е")
        for suffix in (
            "иями", "ями", "ами", "ого", "ему", "ому", "ыми", "ими",
            "ной", "ные", "ная", "ное", "ых", "их",
            "ов", "ев", "ей", "ам", "ям", "ах", "ях",
            "ия", "ие", "ый", "ий", "ая", "ое", "ые",
            "а", "я", "ы", "и", "е", "у", "ю", "ом", "ем",
        ):
            if len(text) > len(suffix) + 3 and text.endswith(suffix):
                return text[: -len(suffix)]
        return text

    def _is_short_requirement(self, value: str) -> bool:
        return len(self._stem_tokens(value)) <= 2
