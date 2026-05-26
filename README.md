# AI Career Copilot for HH

AI-копилот для соискателя для:
- импорта и анализа вакансий
- профиля кандидата и банка достижений
- ATS-совместимого адаптированного резюме
- генерации сопроводительных писем
- проверки с участием человека
- подготовки к собеседованиям
- отслеживания откликов

## Схема проекта

Подробная схема и структура каталогов находятся в [docs/project-structure.md](docs/project-structure.md).
Streamlit frontend уже разнесён по `frontend/streamlit/app.py`, `pages/`, `flows/`, `components/` и `ui/`, поэтому `app.py` теперь только собирает экран и делегирует рендеринг.

## Локальный запуск

### 1. Скопируйте переменные окружения

```powershell
cp .env.example .env
```

### 2. Создайте и активируйте виртуальное окружение

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Установите зависимости

```powershell
pip install -e ".[dev,frontend]"
```

### 4. Поднимите локальный stack

Один шаг для Docker Compose, миграций и health-check:

```powershell
make local-start
```

Если вы поднимаете backend поверх уже существующей базы данных, сначала проверьте актуальность схемы:

```powershell
python -m alembic upgrade head
```

Backend API по умолчанию:

```text
http://localhost:8000/api/v1
```

Примеры новых API путей:

- `POST /api/v1/career-copilot/run` — создание новой pipeline execution
- `GET /api/v1/career-copilot/run/{execution_id}` — получение полного career copilot run с прогрессом, артефактами, readiness, tasks и review status
- `GET /api/v1/review-workspaces/{workspace_id}` — получение review workspace для human-in-the-loop review

OpenAPI:

```text
http://localhost:8000/docs
```

### 5. Запустите Streamlit frontend

В отдельном PowerShell-окне:

```powershell
.\.venv\Scripts\Activate.ps1
streamlit run .\frontend\streamlit\app.py
```

В сайдбаре Streamlit теперь есть два режима авторизации:

- `Вход` для существующего пользователя;
- `Регистрация` для создания нового локального пользователя через `POST /api/v1/auth/register`.

После регистрации нужно переключиться обратно на `Вход` и войти тем же email и паролем.

Если нужен контролируемый demo-state после старта, выполните:

```powershell
python scripts/reset_demo_environment.py
```

Если backend запущен не на стандартном адресе, можно указать API URL через переменную окружения:

```powershell
$env:CAREER_COPILOT_API_BASE_URL = "http://localhost:8000/api/v1"
streamlit run .\frontend\streamlit\app.py
```

`frontend/streamlit/app.py` остаётся единственной точкой входа для UI, а весь сценарий собран из модулей `pages/`, `flows/`, `components/` и `ui/`.

## Проверки

Быстрая проверка backend и frontend-файла:

```powershell
python -m compileall .\frontend\streamlit
pytest -q
python .\scripts\smoke_mvp_flow.py
```

Ожидаемый baseline:

- `python -m compileall .\frontend\streamlit`: без ошибок
- `pytest`: без падений
- `smoke_mvp_flow.py`: `MVP SMOKE PASSED`

## MVP flow

Текущий MVP-сценарий:

резюме
→ импорт и извлечение профиля
→ извлечение достижений
→ импорт вакансии
→ анализ вакансии
→ адаптированное резюме
→ сопроводительное письмо
→ подтверждение документов человеком
→ создание внутренней записи отклика
→ ручная отметка `submitted`
→ подготовка к интервью
→ ответы + feedback + readiness score

## Human-in-the-loop boundary

Проект является candidate-side AI copilot, а не сервисом скрытой автоматизации откликов.

Система не делает:

- автоподачу откликов на HH
- хранение логинов и паролей HH
- скрытую браузерную автоматизацию
- массовый скрейпинг
- генерацию ложных достижений, метрик и опыта

Система делает:

- готовит материалы
- показывает draft-документы
- требует human review
- создаёт внутреннюю запись отклика
- позволяет пользователю вручную отметить, что отклик был отправлен

## Runbook

Подробный MVP runbook находится в [MVP_RUNBOOK.md](MVP_RUNBOOK.md).

Дополнительная локальная проверка backend описана в [RUNBOOK.md](RUNBOOK.md).

Контракт провайдеров LLM зафиксирован в [docs/llm_provider_contract.md](docs/llm_provider_contract.md).
Streamlit smoke checklist: [docs/streamlit_smoke_checklist.md](docs/streamlit_smoke_checklist.md).

## Portfolio / Demo Package

Для advisor demo, portfolio video и controlled pilot walkthrough используйте:

- [docs/portfolio/index.md](docs/portfolio/index.md)
- [docs/demo_walkthrough.md](docs/demo_walkthrough.md)
- [docs/architecture/index.md](docs/architecture/index.md)

В пакете есть:

- deterministic 5-7 minute walkthrough;
- architecture diagram;
- trust flow diagram;
- media checklist for screenshots and GIFs;
- clear `what to show` / `what not to claim` guidance.
