# MVP Runbook - AI Career Copilot for HH

Этот runbook фиксирует текущий рабочий baseline MVP.

## Baseline

Контрольная точка:

```text
tag: mvp-smoke-pass-2026-04-27
```

Ожидаемые проверки:

```text
python -m py_compile frontend/streamlit/app.py: OK
pytest -q: 66 passed
scripts/smoke_mvp_flow.py: MVP SMOKE PASSED
```

## Product Boundary

Проект - candidate-side AI copilot.

Система помогает кандидату:

- разобрать резюме
- извлечь профиль и достижения
- разобрать вакансию
- подготовить адаптированное резюме
- подготовить сопроводительное письмо
- проверить документы перед использованием
- создать внутреннюю запись отклика
- подготовиться к интервью

Система не делает:

- автоматическую отправку откликов
- скрытую автоматизацию сайта HH
- хранение логинов и паролей HH
- массовый скрейпинг
- выдумывание опыта, достижений или метрик

Все сильные утверждения должны быть подтверждены пользователем или помечены как требующие подтверждения.

Текущее MVP-правило для достижений:

- извлеченные достижения сначала получают `fact_status = needs_confirmation`
- пользователь проверяет и редактирует достижения в Streamlit
- только достижения со статусом `confirmed` могут использоваться как сильные утверждения в документах
- backend-генерация резюме и сопроводительного письма дополнительно фильтрует достижения и использует только `confirmed`

## Local Prerequisites

Требуется:

- Python 3.11+
- PostgreSQL
- PowerShell

Опционально:

- `uv`

## Setup

Из корня проекта:

```powershell
cd "D:\python projects\career-copilot"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev,frontend]"
cp .env.example .env
alembic upgrade head
```

## Start Backend

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

Проверка:

```text
http://localhost:8000/docs
```

API base URL:

```text
http://localhost:8000/api/v1
```

## Start Frontend

В отдельном PowerShell-окне:

```powershell
cd "D:\python projects\career-copilot"
.\.venv\Scripts\Activate.ps1
streamlit run .\frontend\streamlit\app.py
```

Если нужен нестандартный backend URL:

```powershell
$env:CAREER_COPILOT_API_BASE_URL = "http://localhost:8000/api/v1"
streamlit run .\frontend\streamlit\app.py
```

## Smoke Checks

Перед smoke backend должен быть запущен.

```powershell
python -m py_compile .\frontend\streamlit\app.py
pytest -q
python .\scripts\smoke_mvp_flow.py
```

Ожидаемый результат:

- `66 passed`
- `MVP SMOKE PASSED`

## MVP Smoke Flow

Smoke script проверяет backend API baseline:

1. upload resume
2. import resume
3. extract structured profile
4. extract achievements
5. import vacancy
6. analyze vacancy
7. generate resume
8. generate cover letter
9. approve resume
10. approve cover letter
11. create application
12. duplicate application protection
13. update application status to submitted
14. create interview session
15. submit interview answers

Важно: API smoke не подтверждает достижения вручную. Это допустимо, потому что backend document generation теперь не использует `needs_confirmation` achievements в `selected_achievements` и `rendered_text`.

## Expected Deterministic Vacancy Analysis

Smoke vacancy:

Требования:

- Python
- FastAPI
- PostgreSQL

Будет плюсом:

- Redis
- Docker

Expected analysis:

- must_have:
  - Python
  - FastAPI
  - PostgreSQL
- nice_to_have:
  - Redis
  - Docker
- strengths:
  - Python
  - FastAPI
  - Docker
- gaps:
  - PostgreSQL
  - Redis
- match_score: 64

## Expected Achievement Review Lifecycle

After achievement extraction:

- `fact_status`: `needs_confirmation`
- `evidence_note`: auto-extraction note
- achievement can be edited and reviewed through Streamlit
- backend endpoint: `PATCH /profile/achievements/{achievement_id}/review`

Allowed fact statuses:

- `needs_confirmation`
- `confirmed`

Streamlit behavior:

- step 5, vacancy import, is blocked until all extracted achievements are `confirmed`
- user can edit achievement title and evidence note before confirmation
- UI labels are localized, while backend keeps technical values

Backend safety behavior:

- resume generation uses only `confirmed` achievements
- cover letter generation uses only `confirmed` achievements
- `needs_confirmation` achievements are not rendered into documents as relevant projects
- document generation is not blocked by unconfirmed achievements; unsupported achievements are simply excluded

## Expected Document Lifecycle

Generated resume:

- `document_kind`: `resume`
- `review_status`: `draft`
- `version_label`: `resume_draft_v2_review_ready`
- `is_active`: `false`

After review:

- `review_status`: `approved`
- `is_active`: `true`

## Expected Document Export

Approved documents can be exported from backend and Streamlit.

Backend endpoints:

- `GET /documents/{document_id}/export/txt`
- `GET /documents/{document_id}/export/md`

Expected behavior:

- export is available only for documents owned by the current user
- export is intended for reviewed/approved document usage
- TXT export returns plain ATS-safe text
- MD export returns markdown-friendly text
- current MVP does not generate DOCX/PDF as the primary export format yet

Generated cover letter:

- `document_kind`: `cover_letter`
- `review_status`: `draft`
- `version_label`: `cover_letter_draft_v1`
- `is_active`: `false`

After review:

- `review_status`: `approved`
- `is_active`: `true`

## Expected Application Lifecycle

Create application:

- `status`: `draft`
- `channel`: `manual`
- `applied_at`: `null`

Duplicate protection:

- second `POST /applications` for the same vacancy returns HTTP 409
- detail: `application already exists for this vacancy`

Manual submitted mark:

- `status`: `submitted`
- `applied_at`: `now()`
- `notes`: `Submitted manually on HH`

This is only an internal status update. It does not send anything to HH.

## Expected Application Status Flow

Allowed statuses:

- `draft`
- `submitted`
- `interview`
- `rejected`
- `offer`

Allowed transitions:

- `draft` -> `submitted`
- `submitted` -> `interview`
- `submitted` -> `rejected`
- `submitted` -> `offer`
- `interview` -> `rejected`
- `interview` -> `offer`

Final statuses:

- `rejected`
- `offer`

Invalid transitions are rejected by backend with HTTP 400.

## Expected Application Dashboard

Streamlit includes an application dashboard tab.

Current dashboard behavior:

- loads applications from `GET /applications`
- displays application status, dates and notes
- shows basic status metrics
- remains internal/read-only for MVP
- does not submit anything to HH or external job boards

## Expected Interview Prep Lifecycle

Create session after submitted application:

- `status`: `draft`
- `question_count`: `12`

Expected question types:

- `role_overview`
- `must_have_requirement`
- `gap_preparation`
- `strength_deep_dive`
- `achievement_star_story`

After submitting 2 answers out of 12:

- `status`: `answered`
- `score_version`: `deterministic_v2`
- `question_count`: `12`
- `answered_count`: `2`
- `unanswered_count`: `10`
- `warning_count`: `0`
- `readiness_score`: `20`

## Known Limitations

Current MVP intentionally uses deterministic/rule-based logic.

Known limitations:

- profile extraction is heuristic
- two-column resumes can still be noisy
- achievements are extracted conservatively
- metrics/results are not inferred automatically
- achievement confirmation is manual and currently handled in Streamlit
- Streamlit interview answer editor covers the full generated question set; smoke/demo still fills only 2 answers
- LLM orchestration layer is not the default path yet

- document export currently supports TXT/MD, not polished DOCX/PDF
- application dashboard is intentionally minimal and mostly read-only

## Safe Next Vertical Slices

Recommended next steps after this baseline:

1. Better structured profile extraction
2. Full interview answer editor for all questions
3. Richer application dashboard: filters, status actions and vacancy/company columns
4. DOCX export for approved documents
5. Better structured profile extraction
6. Richer achievement proof model: STAR fields, metrics and evidence sources
7. LLM layer using extract facts first -> validate -> generate later

Do not add auto-apply, hidden browser automation, or credential storage.
