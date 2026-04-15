# Структура проекта

Этот документ описывает текущую структуру `career-copilot`, роли папок и то, как сейчас проходят основные запросы внутри backend.

## Общая архитектура

```mermaid
flowchart TD
    U[Пользователь] --> API[FastAPI app]
    API --> RT[API router]
    RT --> R1[health]
    RT --> R2[files]
    RT --> R3[profile]
    RT --> R4[vacancies]
    RT --> R5[documents]
    RT --> R6[applications]

    R2 --> S1[SourceFileService]
    R3 --> S2[ProfileImportService / ProfileStructuringService / AchievementExtractionService]
    R4 --> S3[VacancyImportService / VacancyAnalysisService]
    R5 --> S4[ResumeGenerationService / CoverLetterGenerationService / DocumentReviewService]
    R6 --> S5[ApplicationTrackingService]

    S1 --> REP[repositories]
    S2 --> REP
    S3 --> REP
    S4 --> REP
    S5 --> REP
    REP --> DB[(PostgreSQL)]

    API --> CFG[app/core/config.py]
    API --> LOG[app/core/logging.py]
    API --> DBS[app/db/session.py]
    API --> ALEMBIC[Alembic migrations]
```

## Корневая структура

```text
career-copilot/
├── README.md
├── pyproject.toml
├── alembic.ini
├── .env.example
├── build_backend.py
├── Dockerfile
├── api.out.log
├── api.err.log
├── app/
├── alembic/
├── docs/
├── infra/
└── tests/
```

## Папка `app/`

Основной backend-код. Здесь живут HTTP-роуты, сервисы, модели, репозитории, схемы и инфраструктурные модули.

```text
app/
├── __init__.py
├── main.py
├── api/
├── core/
├── db/
├── models/
├── repositories/
├── schemas/
├── services/
├── tasks/
└── workflows/
```

### `app/main.py`

Точка входа FastAPI-приложения.

- создает приложение через `create_app()`
- поднимает `lifespan`
- включает основной router из `app/api/router.py`
- использует настройки из `app/core/config.py`

### `app/api/`

HTTP-слой приложения.

```text
app/api/
├── router.py
└── routes/
    ├── health.py
    ├── files.py
    ├── profile.py
    ├── vacancies.py
    ├── documents.py
    └── applications.py
```

- `router.py` собирает все роутеры в общий API.
- `routes/health.py` отвечает за healthcheck.
- `routes/files.py` принимает upload файлов.
- `routes/profile.py` запускает импорт резюме, структурирование профиля и извлечение достижений.
- `routes/vacancies.py` импортирует вакансии и запускает анализ.
- `routes/documents.py` генерирует резюме, cover letter и выполняет review документов.
- `routes/applications.py` создает и читает application records.

### `app/core/`

Общие настройки и сквозные сервисы.

```text
app/core/
├── config.py
└── logging.py
```

- `config.py` хранит Pydantic settings.
- `logging.py` настраивает логирование для приложения.

### `app/db/`

База данных и session management.

```text
app/db/
├── base.py
└── session.py
```

- `base.py` содержит SQLAlchemy Base.
- `session.py` создает `engine`, `AsyncSessionLocal` и dependency `get_db_session`.

### `app/models/`

ORM-модели предметной области.

```text
app/models/
├── __init__.py
└── entities.py
```

`entities.py` содержит основные таблицы:

- `User`
- `CandidateProfile`
- `CandidateExperience`
- `CandidateAchievement`
- `SourceFile`
- `FileExtraction`
- `Vacancy`
- `VacancyAnalysis`
- `DocumentVersion`
- `ApplicationRecord`
- `InterviewSession`
- `AIRun`

### `app/repositories/`

Слой доступа к данным. Здесь находятся SQLAlchemy-запросы и операции CRUD.

```text
app/repositories/
├── user_repository.py
├── source_file_repository.py
├── file_extraction_repository.py
├── candidate_profile_repository.py
├── candidate_achievement_repository.py
├── vacancy_repository.py
├── vacancy_analysis_repository.py
├── document_version_repository.py
└── application_record_repository.py
```

Назначение основных репозиториев:

- `user_repository.py` - поиск и создание пользователей.
- `source_file_repository.py` - загрузка и чтение исходных файлов.
- `file_extraction_repository.py` - работа с извлечением текста из файлов.
- `candidate_profile_repository.py` - профиль кандидата и связанные данные.
- `candidate_achievement_repository.py` - замена/создание достижений.
- `vacancy_repository.py` - вакансии.
- `vacancy_analysis_repository.py` - анализ вакансий.
- `document_version_repository.py` - версии документов и активные черновики.
- `application_record_repository.py` - application records.

### `app/schemas/`

Pydantic-модели для request/response.

```text
app/schemas/
├── source_file.py
├── profile_import.py
├── profile_structured.py
├── achievement_extract.py
├── vacancy.py
├── document.py
└── application.py
```

Что покрывают схемы:

- `source_file.py` - read-модель файла.
- `profile_import.py` - импорт резюме из файла.
- `profile_structured.py` - результат структурирования профиля.
- `achievement_extract.py` - результат извлечения достижений.
- `vacancy.py` - импорт и чтение вакансий, а также анализ.
- `document.py` - генерация и review документов.
- `application.py` - создание, чтение и обновление заявок.

### `app/services/`

Бизнес-логика. Роуты минимальны и делегируют основную работу сюда.

```text
app/services/
├── storage_service.py
├── resume_parser_service.py
├── source_file_service.py
├── profile_import_service.py
├── profile_structuring_service.py
├── achievement_extraction_service.py
├── vacancy_import_service.py
├── vacancy_analysis_service.py
├── resume_generation_service.py
├── cover_letter_generation_service.py
├── document_review_service.py
└── application_tracking_service.py
```

Кратко по ответственности:

- `storage_service.py` - чтение и запись файлов в object storage.
- `resume_parser_service.py` - парсинг резюме.
- `source_file_service.py` - загрузка файла, поиск пользователя и создание source file.
- `profile_import_service.py` - запуск импорта профиля из source file.
- `profile_structuring_service.py` - извлечение структурированных данных и опыта.
- `achievement_extraction_service.py` - извлечение достижений из raw текста.
- `vacancy_import_service.py` - импорт вакансии из текста или URL.
- `vacancy_analysis_service.py` - анализ вакансии и сопоставление с профилем.
- `resume_generation_service.py` - генерация резюме под вакансию.
- `cover_letter_generation_service.py` - генерация cover letter.
- `document_review_service.py` - изменение review-статуса документа.
- `application_tracking_service.py` - создание и список заявок, обновление статусов.

### `app/tasks/` и `app/workflows/`

Сейчас это заготовки под фоновые задачи и более крупные сценарии.

- `app/tasks/` - место для background jobs.
- `app/workflows/` - место для orchestration-слоя, если логика станет многошаговой.

## Папка `alembic/`

Миграции базы данных.

```text
alembic/
├── env.py
├── script.py.mako
└── versions/
    ├── 9de02e41efad_initial_schema.py
    └── c5e1b2062553_add_file_extractions.py
```

- `env.py` подключает Alembic к модели и настройкам проекта.
- `versions/` хранит миграции схемы.

## Папка `infra/`

Инфраструктурные файлы.

```text
infra/
└── docker/
    └── docker-compose.yml
```

В этой папке лежит локальная docker-compose конфигурация для запуска сервисов окружения.

## Папка `tests/`

Тесты проекта.

```text
tests/
└── test_health.py
```

Сейчас есть только базовый healthcheck-тест через `TestClient`. `conftest.py` пока отсутствует.

## Основные потоки данных

### 1. Загрузка файла

1. Клиент вызывает `POST /files/upload`.
2. `app/api/routes/files.py` передает запрос в `SourceFileService`.
3. `SourceFileService` находит или создает `User` по email.
4. Файл сохраняется в storage.
5. В базе создается `SourceFile`.

### 2. Импорт и структурирование резюме

1. Клиент вызывает `POST /profile/import-resume`.
2. `ProfileImportService` берет `SourceFile`, скачивает файл и парсит текст.
3. Создается `FileExtraction`.
4. Далее `POST /profile/extract-structured` запускает `ProfileStructuringService`.
5. Сервис заполняет `CandidateProfile` и `CandidateExperience`.

### 3. Извлечение достижений

1. Клиент вызывает `POST /profile/extract-achievements`.
2. `AchievementExtractionService` читает `FileExtraction`.
3. Из текста формируются `CandidateAchievement`.

### 4. Вакансии

1. Клиент вызывает `POST /vacancies/import`.
2. `VacancyImportService` ищет или создает пользователя.
3. Создается `Vacancy`.
4. Затем `POST /vacancies/{id}/analyze` запускает `VacancyAnalysisService`.
5. Результат сохраняется в `VacancyAnalysis`.

### 5. Генерация документов

1. Клиент вызывает `POST /documents/resumes/generate` или `POST /documents/letters/generate`.
2. Сервисы читают вакансию, профиль и анализ.
3. Создается `DocumentVersion`.

### 6. Заявки

1. Клиент вызывает `POST /applications`.
2. `ApplicationTrackingService` создаёт `ApplicationRecord`.
3. `GET /applications` возвращает список заявок пользователя.

## Ключевые таблицы и связи

- `users`
  - базовая сущность пользователя
  - связана с профилем, файлами, вакансиями, документами и заявками
- `candidate_profiles`
  - один профиль на одного пользователя
- `candidate_experiences`
  - список опыта внутри профиля
- `candidate_achievements`
  - список достижений внутри профиля
- `source_files`
  - загруженные исходные файлы
- `file_extractions`
  - извлеченный текст и метаданные
- `vacancies`
  - вакансии пользователя
- `vacancy_analyses`
  - результаты анализа вакансии
- `document_versions`
  - черновики и версии резюме/cover letter
- `application_records`
  - история заявок

## Что уже есть и что еще заготовлено

Есть:

- весь основной CRUD и доменная логика по профилю, вакансиям, документам и заявкам
- PostgreSQL-схема через SQLAlchemy и Alembic
- базовый healthcheck

Заготовлено:

- отдельный слой авторизации и `current_user` dependency
- `conftest.py` с общими фикстурами
- фоновые задачи в `tasks/`
- orchestration-слой в `workflows/`

## Текущий healthcheck

- `GET /health`
- ожидаемый ответ: `{"status":"ok"}`
