# app\domain\skills\catalog.py

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SkillDefinition:
    canonical_name: str
    patterns: list[str]
    related_skills: list[str]


SKILL_DEFINITIONS: list[SkillDefinition] = [
    SkillDefinition(
        canonical_name="Python",
        patterns=[r"\bpython\b", r"\bпитон\b"],
        related_skills=[],
    ),
    SkillDefinition(
        canonical_name="SQL",
        patterns=[
            r"\bsql\b",
            r"\bсубд\b",
            r"баз[аы]\s+данных",
        ],
        related_skills=["PostgreSQL"],
    ),
    SkillDefinition(
        canonical_name="API",
        patterns=[
            r"\bapi\b",
            r"\brest\b",
            r"rest\s*api",
            r"интеграц\w*\s+с\s+api",
        ],
        related_skills=["FastAPI"],
    ),
    SkillDefinition(
        canonical_name="FastAPI",
        patterns=[
            r"\bfastapi\b",
            r"fast\s*api",
        ],
        related_skills=[],
    ),
    SkillDefinition(
        canonical_name="PostgreSQL",
        patterns=[
            r"\bpostgres(?:ql)?\b",
            r"\bpostgresql\b",
        ],
        related_skills=[],
    ),
    SkillDefinition(
        canonical_name="Git",
        patterns=[r"\bgit\b", r"\bgithub\b", r"\bgitlab\b"],
        related_skills=[],
    ),
    SkillDefinition(
        canonical_name="Redis",
        patterns=[r"\bredis\b"],
        related_skills=[],
    ),
    SkillDefinition(
        canonical_name="Docker",
        patterns=[
            r"\bdocker\b",
            r"\bконтейнеризац",
        ],
        related_skills=[],
    ),
    SkillDefinition(
        canonical_name="SQLAlchemy",
        patterns=[r"\bsqlalchemy\b", r"sql\s*alchemy"],
        related_skills=[],
    ),
    SkillDefinition(
        canonical_name="Alembic",
        patterns=[r"\balembic\b"],
        related_skills=[],
    ),
    SkillDefinition(
        canonical_name="Pydantic",
        patterns=[r"\bpydantic\b"],
        related_skills=[],
    ),
    SkillDefinition(
        canonical_name="Pytest",
        patterns=[
            r"\bpytest\b",
            r"\bunit\s+tests?\b",
            r"\bтестировани[ея]\b",
        ],
        related_skills=[],
    ),
    SkillDefinition(
        canonical_name="Celery",
        patterns=[r"\bcelery\b"],
        related_skills=[],
    ),
    SkillDefinition(
        canonical_name="AsyncIO",
        patterns=[r"\basyncio\b", r"\basync\b", r"асинхрон"],
        related_skills=[],
    ),
    SkillDefinition(
        canonical_name="LLM",
        patterns=[
            r"\bllm\b",
            r"large language model",
            r"языков(?:ая|ые)\s+модел",
        ],
        related_skills=[],
    ),
    SkillDefinition(
        canonical_name="Prompt Engineering",
        patterns=[
            r"prompt engineering",
            r"prompting",
            r"промптинг",
            r"промпт-инж",
        ],
        related_skills=[],
    ),
    SkillDefinition(
        canonical_name="Data Science",
        patterns=[r"data science", r"data scientist", r"анализ\s+данных"],
        related_skills=[],
    ),
    SkillDefinition(
        canonical_name="Machine Learning",
        patterns=[r"machine learning", r"\bml\b", r"машинн(?:ое|ого)\s+обуч"],
        related_skills=[],
    ),
    SkillDefinition(
        canonical_name="TensorFlow",
        patterns=[r"\btensorflow\b"],
        related_skills=[],
    ),
    SkillDefinition(
        canonical_name="PyTorch",
        patterns=[r"\bpytorch\b"],
        related_skills=[],
    ),
    SkillDefinition(
        canonical_name="Pandas",
        patterns=[r"\bpandas\b"],
        related_skills=[],
    ),
    SkillDefinition(
        canonical_name="NumPy",
        patterns=[r"\bnumpy\b"],
        related_skills=[],
    ),
    SkillDefinition(
        canonical_name="Scikit-learn",
        patterns=[r"scikit-learn", r"sklearn"],
        related_skills=[],
    ),
    SkillDefinition(
        canonical_name="NLP",
        patterns=[r"\bnlp\b", r"обработк[аи]\s+текста"],
        related_skills=[],
    ),
    SkillDefinition(
        canonical_name="RAG",
        patterns=[r"\brag\b", r"retrieval[-\s]?augmented"],
        related_skills=[],
    ),
]
