# app\domain\requirement_models.py

from dataclasses import dataclass


@dataclass(slots=True)
class VacancyRequirement:
    """Требование вакансии с приоритетом."""
    text: str
    keyword: str | None = None
    priority: str = "important"  # critical | important | optional
