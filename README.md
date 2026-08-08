````markdown
# 🚀 Career Copilot

### AI Career Assistant for Job Search

Career Copilot — AI-копилот для соискателя, который помогает
анализировать вакансии, структурировать опыт кандидата,
адаптировать документы под конкретную вакансию и подготовиться
к собеседованию.

Проект объединяет детерминированную бизнес-логику, LLM,
работу с документами и human-in-the-loop workflow.

> **Career Copilot — candidate-side AI assistant, а не сервис
> автоматической подачи откликов.**

---

## 🎯 Problem

Подготовка качественного отклика на вакансию требует ручной работы:

- анализа требований вакансии;
- сопоставления требований с опытом кандидата;
- поиска релевантных достижений;
- адаптации резюме;
- подготовки сопроводительного письма;
- проверки документов;
- подготовки к собеседованию.

Career Copilot объединяет эти этапы в единый workflow.

---

## 💡 Solution

Основной MVP workflow:

```text
Resume
   ↓
Profile Extraction
   ↓
Achievement Bank
   ↓
Vacancy Import
   ↓
Vacancy Analysis
   ↓
Requirement Matching
   ↓
Tailored Resume
   ↓
Cover Letter
   ↓
Human Review
   ↓
Application Tracking
   ↓
Interview Preparation
````

Система не пытается полностью заменить кандидата.

Она подготавливает материалы и помогает принимать решения,
оставляя финальные действия за пользователем.

---

# ✨ Key Features

### 👤 Candidate Profile

* импорт резюме;
* извлечение профиля кандидата;
* структурирование опыта;
* формирование банка достижений.

### 🔎 Vacancy Analysis

* импорт вакансий;
* анализ требований;
* нормализация требований;
* сопоставление требований с профилем кандидата.

### 📝 Document Generation

* создание адаптированного резюме;
* ATS-oriented formatting;
* генерация сопроводительного письма;
* использование подтверждённых данных кандидата.

### 👀 Human-in-the-loop Review

Пользователь получает возможность проверить
сгенерированные материалы перед использованием.

Review Workspace позволяет работать с draft-документами
и контролировать результат AI-генерации.

### 🎤 Interview Preparation

* подготовка к интервью;
* генерация вопросов и ответов;
* feedback;
* readiness score.

### 📋 Application Tracking

После ручной отправки отклика пользователь может
создать внутреннюю запись и отметить статус:

```text
submitted
```

---

# 🧠 AI Approach

Одна из ключевых особенностей проекта — разделение
детерминированной логики и LLM.

### Deterministic Layer

Используется для задач, где важны предсказуемость,
структура и контроль:

* извлечение и нормализация данных;
* анализ требований;
* matching;
* readiness calculations;
* контроль workflow;
* валидация структурированных данных.

### LLM Layer

Используется там, где требуется работа с естественным языком:

* генерация сопроводительных писем;
* формирование и улучшение текстов;
* подготовка материалов к интервью;
* языковая обработка.

### Prompt Engineering

LLM не получает задачу в виде одного универсального prompt.

В проекте используются специализированные сценарии
генерации и структурированные входные данные.

Цель — получать воспроизводимый результат,
ограниченный фактическими данными кандидата.

---

# 🛡️ Trust & Human-in-the-loop

Career Copilot придерживается принципа:

> **AI prepares — human decides.**

Система не должна создавать фиктивный опыт кандидата
ради повышения соответствия вакансии.

### Система не делает

* ❌ автоподачу откликов на HH;
* ❌ хранение логинов и паролей HH;
* ❌ скрытую браузерную автоматизацию;
* ❌ массовый скрейпинг;
* ❌ генерацию ложных достижений;
* ❌ генерацию выдуманных метрик и опыта.

### Система делает

* ✅ анализирует входные данные;
* ✅ готовит draft-документы;
* ✅ показывает результат пользователю;
* ✅ требует human review;
* ✅ создаёт внутреннюю запись отклика;
* ✅ позволяет вручную отметить отправленный отклик.

---

# 🏗️ Architecture

Проект построен вокруг backend API и Streamlit frontend.

Основные компоненты:

```text
                    ┌──────────────────────┐
                    │   Streamlit Frontend │
                    │                      │
                    │ pages / flows /      │
                    │ components / ui      │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │      FastAPI API     │
                    └──────────┬───────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
       Candidate/Profile   Vacancy        Document/Review
              │                │                │
              └────────────────┼────────────────┘
                               ▼
                    ┌──────────────────────┐
                    │   Career Copilot     │
                    │      Pipeline        │
                    └──────────┬───────────┘
                               │
                    ┌──────────┴──────────┐
                    ▼                     ▼
             Deterministic Layer      LLM Layer
                    │                     │
                    └──────────┬──────────┘
                               ▼
                    Generated Artifacts
```

Подробная структура проекта:

[docs/project-structure.md](https://github.com/Alexsey111/career-copilot/blob/v2/docs/project-structure.md)

Архитектурная документация:

[docs/architecture/](https://github.com/Alexsey111/career-copilot/tree/v2/docs/architecture)

---

# 🖥️ Frontend

Streamlit frontend организован по функциональным областям:

```text
frontend/streamlit/
├── app.py
├── pages/
├── flows/
├── components/
└── ui/
```

`app.py` является точкой входа и собирает экран,
делегируя функциональность специализированным модулям.

---

# 🔌 API

Основные API endpoints:

### Create Career Copilot Run

```http
POST /api/v1/career-copilot/run
```

Создаёт новую pipeline execution.

### Get Career Copilot Run

```http
GET /api/v1/career-copilot/run/{execution_id}
```

Возвращает состояние выполнения pipeline,
прогресс, артефакты, readiness, tasks и review status.

### Review Workspace

```http
GET /api/v1/review-workspaces/{workspace_id}
```

Возвращает workspace для human-in-the-loop review.

### OpenAPI

После запуска backend:

```text
http://localhost:7000/docs
```

---

# 🧩 MVP Flow

Текущий MVP реализует следующий сценарий:

```text
Резюме
  ↓
Импорт и извлечение профиля
  ↓
Извлечение достижений
  ↓
Импорт вакансии
  ↓
Анализ вакансии
  ↓
Адаптированное резюме
  ↓
Сопроводительное письмо
  ↓
Подтверждение документов человеком
  ↓
Внутренняя запись отклика
  ↓
Ручная отметка submitted
  ↓
Подготовка к интервью
  ↓
Ответы + feedback + readiness score
```

---

# 📊 Demo Mode

Для локальной демонстрации сервис работает
в demo-режиме.

По умолчанию импорт вакансий ограничен:

```text
3 вакансии / час / пользователь
```

После достижения лимита следующий импорт возвращает:

```text
402 Payment Required
```

с деталями `QuotaErrorDetail` и:

```text
action=vacancy_import
```

Используется скользящее часовое окно.

### Configuration

```env
BILLING_FREE_TIER_VACANCY_IMPORTS_LIMIT=3
DEMO_VACANCY_IMPORT_WINDOW_SECONDS=3600
```

Платный план `paid_monthly` с активной подпиской
не ограничивается этой квотой.

Важно:

> Ограничение применяется только к импорту вакансий.
> Поиск вакансий квотой не ограничен.

---

# 🧪 Testing & Validation

Основные проверки:

```bash
python -m compileall .\frontend\streamlit
pytest -q
python .\scripts\smoke_mvp_flow.py
```

Ожидаемый результат:

```text
compileall → без ошибок
pytest     → без падений
smoke      → MVP SMOKE PASSED
```

---

# 🚀 Local Development

## 1. Clone

```bash
git clone https://github.com/Alexsey111/career-copilot.git
cd career-copilot
```

Используется актуальная ветка:

```text
v2
```

---

## 2. Environment

Создайте `.env` из шаблона:

```bash
cp .env.example .env
```

Для PowerShell можно создать файл вручную
на основе `.env.example`.

---

## 3. Virtual Environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

---

## 4. Dependencies

```powershell
pip install -e ".[dev,frontend]"
```

---

## 5. Start Local Stack

```powershell
make local-start
```

Команда поднимает локальный stack,
выполняет необходимые миграции и health-check.

Если backend запускается поверх существующей базы:

```powershell
python -m alembic upgrade head
```

---

## 6. Backend

API:

```text
http://localhost:7000/api/v1
```

OpenAPI:

```text
http://localhost:7000/docs
```

---

## 7. Streamlit

В отдельном PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
make streamlit
```

Frontend будет использовать backend API.

Если backend находится по другому адресу:

```powershell
$env:CAREER_COPILOT_API_BASE_URL = "http://localhost:7000/api/v1"
make streamlit
```

---

# 🔐 Authentication

Streamlit frontend поддерживает два режима:

### Регистрация

Создание нового локального пользователя через:

```http
POST /api/v1/auth/register
```

### Вход

После регистрации пользователь возвращается
в режим `Вход` и авторизуется с тем же email и паролем.

---

# 🧹 Demo Environment

Для controlled demo-state после запуска можно использовать:

```powershell
python scripts/reset_demo_environment.py
```

Это позволяет привести локальное demo-окружение
к контролируемому состоянию перед демонстрацией.

---

# 📚 Documentation

### Project Structure

[docs/project-structure.md](https://github.com/Alexsey111/career-copilot/blob/v2/docs/project-structure.md)

### Architecture

[docs/architecture/](https://github.com/Alexsey111/career-copilot/tree/v2/docs/architecture)

### MVP Runbook

[MVP_RUNBOOK.md](https://github.com/Alexsey111/career-copilot/blob/v2/MVP_RUNBOOK.md)

### Backend Runbook

[RUNBOOK.md](https://github.com/Alexsey111/career-copilot/blob/v2/RUNBOOK.md)

### LLM Provider Contract

[docs/llm_provider_contract.md](https://github.com/Alexsey111/career-copilot/blob/v2/docs/llm_provider_contract.md)

### Streamlit Smoke Checklist

[docs/streamlit_smoke_checklist.md](https://github.com/Alexsey111/career-copilot/blob/v2/docs/streamlit_smoke_checklist.md)

### Portfolio / Demo Package

[docs/portfolio/](https://github.com/Alexsey111/career-copilot/tree/v2/docs/portfolio)

[Demo Walkthrough](https://github.com/Alexsey111/career-copilot/blob/v2/docs/demo_walkthrough.md)

---

# 🎥 Portfolio Demo

Для демонстрации проекта подготовлен отдельный portfolio package.

Он включает:

* deterministic 5–7 minute walkthrough;
* architecture diagram;
* trust flow diagram;
* media checklist;
* сценарий демонстрации;
* `what to show` / `what not to claim` guidance.

Это позволяет демонстрировать проект без необходимости
проходить весь workflow вручную каждый раз.

---

# 📌 Project Status

### 🟢 MVP

Основной MVP pipeline реализован:

```text
Resume
→ Profile
→ Achievements
→ Vacancy
→ Analysis
→ Tailored Resume
→ Cover Letter
→ Human Review
→ Application Tracking
→ Interview Preparation
```

Проект находится в активной разработке.

---

# 🔮 Roadmap

Дальнейшее развитие проекта направлено на:

* расширение анализа вакансий;
* улучшение requirement matching;
* развитие Document Review;
* расширение interview preparation;
* улучшение пользовательского интерфейса;
* развитие AI-assisted workflows.

---

# 👨‍💻 Author

**Alexsey**

AI Developer · Prompt Engineer · AI Automation · Vibe Coder

GitHub: [@Alexsey111](https://github.com/Alexsey111)

````

## Почему именно так

Твой старый README я **не считаю плохим**. Он просто решает другую задачу. В нём много полезного, но первая информация, которую видит человек, — это локальный запуск, структура `frontend/streamlit`, миграции, API, demo quota и runbook.

Для портфолио это переворачиваем:

**было:**

```text
Описание
→ структура
→ запуск
→ API
→ проверки
→ MVP
→ ограничения
→ runbook
````

**становится:**

```text
Что это
→ какую проблему решает
→ как работает
→ что умеет
→ AI approach
→ Trust / HITL
→ архитектура
→ API
→ demo
→ testing
→ запуск
→ документация
```
