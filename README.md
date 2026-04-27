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

### 4. Примените миграции БД

```powershell
alembic upgrade head
```

### 5. Запустите backend

```powershell
uvicorn app.main:app --reload
```

Backend API по умолчанию:

```text
http://localhost:8000/api/v1
```

OpenAPI:

```text
http://localhost:8000/docs
```

### 6. Запустите Streamlit frontend

В отдельном PowerShell-окне:

```powershell
.\.venv\Scripts\Activate.ps1
streamlit run .\frontend\streamlit\app.py
```

Если backend запущен не на стандартном адресе, можно указать API URL через переменную окружения:

```powershell
$env:CAREER_COPILOT_API_BASE_URL = "http://localhost:8000/api/v1"
streamlit run .\frontend\streamlit\app.py
```

## Проверки

Быстрая проверка backend и frontend-файла:

```powershell
python -m py_compile .\frontend\streamlit\app.py
pytest -q
python .\scripts\smoke_mvp_flow.py
```

Ожидаемый baseline:

- `pytest`: `58 passed`
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
