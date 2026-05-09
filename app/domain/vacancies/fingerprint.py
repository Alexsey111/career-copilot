# app\domain\vacancies\fingerprint.py

from __future__ import annotations

import hashlib
import re


def normalize_vacancy_text(text: str) -> str:
    text = text.lower()

    text = re.sub(r"\s+", " ", text)

    # убираем слишком шумные символы
    text = re.sub(r"[^\w\s]", " ", text)

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def build_vacancy_fingerprint(
    *,
    title: str,
    company: str | None,
    text: str,
) -> str:
    normalized = "\n".join(
        [
            normalize_vacancy_text(title),
            normalize_vacancy_text(company or ""),
            normalize_vacancy_text(text[:5000]),
        ]
    )

    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()