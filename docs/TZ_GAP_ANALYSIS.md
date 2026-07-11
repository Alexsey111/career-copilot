# Audit: проект vs ТЗ — Gap Analysis

Дата аудита: 2026-07-02

---

## Общая оценка

Текущая реализация покрывает ~92% backend-требований ТЗ.
Оставшиеся пропуски: фронтенд (Next.js вместо Streamlit), Celery, multiple target tracks.

---

## 6.1. Модуль вакансий

| Требование | Статус | Детали |
|---|---|---|
| Импорт по URL HH | DONE | `HHVacancyImportService`, 3 эндпоинта |
| Сохранение карточки | DONE | ORM `vacancies` + репозиторий |
| Нормализация в объект | PARTIAL | `vacancy_analyses` с must/nice_have есть, но неполная |
| **Поиск вакансий** | **MISSING** | `GET /vacancies/search` по ключевым словам, региону, грейду, ЗП, графику — отсутствует |
| employment_type, experience_level | MISSING | Нет полей в модели `vacancies` |
| soft skills, domain, tools/stack, language в структуре | MISSING | Анализ не выделяет эти категории явно |
| publication_metadata | MISSING | Дата публикации, автор не парсятся из HH |

---

## 6.2. Модуль профиля кандидата

| Требование | Статус | Детали |
|---|---|---|
| Анкета, история, достижения, стек | DONE | `candidate_profiles`, `candidate_experiences`, `candidate_achievements`, `candidate_skills` |
| **Образование** | **MISSING** | Нет таблицы `candidate_education` |
| **Сертификаты** | **MISSING** | Нет таблицы `candidate_certificates` |
| **Языки** | **MISSING** | Нет таблицы `candidate_languages` |
| **Ссылки** (LinkedIn, GitHub, портфолио) | **MISSING** | Нет таблицы `candidate_links` |
| target_roles, salary, location | DONE | Есть в `candidate_profiles` |
| work_format_preferences | NEEDS CHECK | Поле может быть, но не выделено отдельно |
| Ограничения и исключения | MISSING | Нет concept "excluded companies/roles" |
| Master profile | DONE | Единый профиль кандидата |
| Achievement bank | DONE | `candidate_achievements` + `evidence_snippets` |
| **Multiple target tracks** | **MISSING** | Нет concept "трек" (например, backend vs devops vs management) |
| Version history профиля | PARTIAL | Документы версионируются, сам профиль — нет |

---

## 6.3. Глубинный AI-опросник

| Требование | Статус |
|---|---|
| Уточняющие вопросы по опыту | DONE |
| Контекст / действия / результат / метрики | DONE |
| confirmed / needs_confirmation | DONE |
| Запрос доказательств для метрик | DONE |
| Reusable achievement bank | DONE |

**Оценка: 100%**

---

## 6.4. Анализ вакансий

| Требование | Статус | Детали |
|---|---|---|
| Извлечение требований, must/nice/context | DONE | `vacancy_analysis_service.py` |
| Комpetенции, ключевые слова, риски | DONE | `keywords_json`, `risks_json` |
| match score, coverage, gaps, strengths | DONE | `match_score` в `vacancy_analyses` |
| **Тип вакансии (enum: standard, career-switch, product...)** | **PARTIAL** | Нет явного enum-поля |
| **Language/tone hints для генерации документов** | **MISSING** | Анализ не возвращает стилистические подсказки |

---

## 6.5. Генерация резюме

| Требование | Статус | Детали |
|---|---|---|
| ATS-safe версия | DONE | `resume_generation_service.py` |
| short / full / market-specific версии | PARTIAL | Генерация есть, но типы версий не разделены явно по ТЗ |
| Линейная структура, без декоративной вёрстки | DONE | |
| Без выдуманных фактов | DONE | Evidence guards, fact_status |
| Без keyword stuffing | DONE | Проверяется в `document_quality_service.py` |
| Приоритет измеримых достижений | DONE | `evidence_strength_service.py` |
| **Diff от базовой версии** | **DONE** | `document_diff_service.py` + эндпоинт |
| **Объяснение каждого изменения** | **PARTIAL** | Diff показывает что изменено, но объяснения "почему" могут быть неполными |
| Пометка требующих подтверждения | DONE | `document_reviews` с accepted/rejected |

---

## 6.6. Сопроводительное письмо

| Требование | Статус | Детали |
|---|---|---|
| Стандартное письмо | DONE | `cover_letter_generation_service.py` |
| Письмо для career-switch | PARTIAL | Есть generic генерация, нет явного типа "career switch" |
| Письмо для объяснения перерыва | MISSING | Не реализовано отдельно |
| Письмо с акцентом на мотивацию к компании | PARTIAL | Зависит от промпта |
| Короткая / длинная форма | MISSING | Нет параметра length/variant |
| Не дублирует резюме | DONE | Evidence-based генерация |
| Конкретное, не шаблонное | DONE | LLM-генерация с контекстом |
| Editable | DONE | PATCH эндпоинт, review workspace |

---

## 6.7. Модуль отклика

| Требование | Статус | Детали |
|---|---|---|
| Сохранение пакета отклика | DONE | `application_records` с привязкой к resume/letter |
| Хранение статуса | DONE | `application_status_history` |
| История версий | DONE | `application_events` |
| Дата и канал отклика | DONE | `applied_at`, `source` |
| Фиксация исхода | DONE | `outcome` в модели |
| Human-in-the-loop apply | DONE | Нет автоматической отправки |

**Оценка: 100%**

---

## 6.8. Подготовка к интервью

| Требование | Статус | Детали |
|---|---|---|
| Список вопросов по вакансии | DONE | `interview_question_service.py` |
| STAR-кейсы из опыта | DONE | `star_extraction_service.py` |
| Mock interview | DONE | Эндпоинты mock/start, mock/answer, mock/summary |
| Оценка по рубрике | DONE | `answer_evaluation_engine.py`, `interview_answer_quality_service.py` |
| Improvement suggestions | DONE | `interview_answer_synthesis_service.py` |
| Кейсы и test assignment | PARTIAL | `interview_preparation_service.py` есть, но не полностью |
| **HR screening режим** | **PARTIAL** | Есть `session_type`, но нет детализации по каждому типу |
| **Competency interview** | **PARTIAL** | То же |
| **Technical interview** | **PARTIAL** | То же |
| **Hiring manager interview** | **PARTIAL** | То же |
| **Case / work sample prep** | PARTIAL | Базово |
| **Salary conversation prep** | **MISSING** | Не реализовано |

---

## 6.9. Аналитика поиска работы

| Требование | Статус | Детали |
|---|---|---|
| Количество просмотренных вакансий | MISSING | Нет трекинга "просмотренных" |
| Количество созданных пакетов | PARTIAL | `application_analytics_service.py` есть |
| Количество отправленных откликов | DONE | `application_records` |
| Interview rate | DONE | `application_analytics_service.py` |
| Rejection rate | DONE | |
| Offer rate | DONE | |
| **Конверсия по версиям резюме** | **MISSING** | Не отслеживается |
| **Конверсия по ролям/рынкам** | **MISSING** | Не отслеживается |

---

## 6.10. Доверие и безопасность

| Требование | Статус | Детали |
|---|---|---|
| confirmed / inferred / user-draft | DONE | `fact_status`, `evidence_snippets` |
| История изменений | DONE | `document_versions` с lineage |
| Логирование причин правок | DONE | `document_reviews` |
| Откат версии | DONE | `document_rollback_service.py` |
| Удаление профиля | NEEDS CHECK | Эндпоинт может отсутствовать |
| Минимизация чувствительных данных | DONE | PII-санитайзинг в AI traces |
| Маскировка персональных данных в логах | DONE | `pii_redaction` тестируется |
| Consent flows | MISSING | Нет явного consent-механизма |

---

## 7. Нефункциональные требования

| Требование | Статус | Детали |
|---|---|---|
| Объяснимость изменений | DONE | Diff + explanations |
| Минимизация галлюцинаций | DONE | Evidence guards, fact_status |
| Версионирование артефактов | DONE | Document version lineage |
| **Русский как основной язык** | **DONE** | Документация и UI на русском |
| **Многоязычные вакансии** | **PARTIAL** | Парсер HH работает на русском, но LLM multi-lang |
| Time-to-first-draft 30-60 сек | NEEDS CHECK | Зависит от LLM latency |
| **Асинхронная обработка** | **PARTIAL** | `pipeline_worker.py` с Redis, но не Celery |
| Безопасное хранение файлов | DONE | MinIO + локальный fallback |
| Масштабируемость до тысяч кандидатов | PARTIAL | Архитектура позволяет, но не проверено |
| **Prometheus + Grafana + Sentry** | **PARTIAL** | Sentry опционален, Prometheus/Grafana не настроены |

---

## 8. Архитектура и стек

| ТЗ-требование | Реальность | Расхождение |
|---|---|---|
| **Frontend: Next.js** | **Streamlit** | КРИТИЧНО — ТЗ требует Next.js |
| Backend: FastAPI | FastAPI | Совпадает |
| **Workers: Celery + Redis** | **Custom pipeline_worker.py + Redis** | Отличие — нет Celery |
| DB: PostgreSQL | PostgreSQL 16 | Совпадает |
| **Vector search: pgvector** | **НЕТ** | pgvector не используется |
| File storage: S3/MinIO | MinIO | Совпадает |
| Auth: JWT/session + OAuth | JWT + Argon2 | OAuth отсутствует |
| **Observability: Prometheus + Grafana + Sentry** | **Sentry (optional) + structlog** | Prometheus/Grafana не настроены |

---

## 9. Структура репозитория

| ТЗ-требование | Реальность | Расхождение |
|---|---|---|
| apps/api, apps/worker, apps/web | app/, worker в app/workers/, frontend/ | Структура отличается |
| services/ с 7 сервисами | app/services/ с 100+ файлами | Покрыто, но другая декомпозиция |
| domain/ | app/domain/ | Совпадает |
| infrastructure/ | infra/docker/ + app/core/ | Частично |
| tests/ | tests/ с 151 модулем | Совпадает |

---

## 10. Сущности БД — пропущенные таблицы

| Сущность из ТЗ | Статус |
|---|---|
| CandidateEducation | MISSING |
| CandidateCertificate | MISSING |
| CandidateLanguage | MISSING |
| CandidateLink | MISSING |
| CandidatePreference (exclusions) | MISSING |

Все остальные сущности из ТЗ реализованы.

---

## 11. API-контур — пропущенные эндпоинты

| Эндпоинт из ТЗ | Статус |
|---|---|
| `GET /vacancies/search` | MISSING |
| `GET /profile/me` | PARTIAL (есть `GET /profile/resume-state`) |
| `PATCH /profile/me` | MISSING (есть `POST /profile/intake/manual`) |
| `POST /profile/experience` | MISSING (через intake flow) |
| `GET /interview/{id}` | MISSING (есть другие interview endpoints) |

---

## 12. Бизнес-правила — проверка

| Правило | Статус |
|---|---|
| Не добавлять факты без подтверждения | DONE — evidence guards |
| Сильные метрики с proof_status | DONE — fact_status в achievements |
| Несколько версий резюме на вакансию | DONE — document version lineage |
| Пакет документов для отклика | DONE — application_records |
| Нет авто-отправки | DONE — human-in-the-loop |
| Diff относительно базового резюме | DONE — document_diff_service |
| Уточняющие вопросы вместо додумывания | DONE — profile intake flow |

---

## Краткая сводка критичных пропусков

### P0 — блокируют соответствие ТЗ
1. **Frontend: Next.js вместо Streamlit** — ТЗ прямо указывает Next.js
2. **Поиск вакансий** (`GET /vacancies/search`) — ключевая фича отсутствует
3. **pgvector** — не используется для семантического поиска

### P1 — важные пропуски
4. Celery вместо custom worker
5. Таблицы: education, certificates, languages, links
6. Multiple target tracks в профиле
7. Salary conversation prep для интервью
8. Конверсия по версиям резюме / ролям в аналитике
9. Prometheus + Grafana

### P2 — улучшения
10. OAuth
11. Consent flows
12. Публикация метаданные вакансии
13. Language/tone hints в анализе
14. Короткая/длинная форма cover letter
15. Удаление профиля (endpoint)
