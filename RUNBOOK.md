# Career Copilot Backend Runbook

Runbook для локальной проверки backend после изменений.

Проект: candidate-side AI Career Copilot for HH.

Основной flow:

```text
resume upload
→ resume import
→ structured profile extraction
→ achievement extraction
→ vacancy import
→ vacancy analysis
→ resume generation
→ cover letter generation
→ human approval
→ application tracking
→ interview preparation
→ interview answer feedback
```

---

## 1. Быстрая проверка тестами

Запуск из корня проекта:

```powershell
pytest -q
```

Ожидаемый текущий baseline:

```text
70 passed
```

Если тесты падают, сначала чинить тесты, потом запускать live smoke.

---

## 2. Live MVP smoke flow

Проверяет живой backend через HTTP.

Backend должен быть запущен на:

```text
http://localhost:8000
```

Запуск:

```powershell
python .\scripts\smoke_mvp_flow.py
```

Ожидаемый финал:

```text
MVP SMOKE PASSED
```

Что проверяет smoke:

```text
1. upload TXT resume
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
12. duplicate application returns 409
13. update application status draft -> submitted
14. create interview session
15. submit interview answers
```

Ключевые ожидаемые значения:

```text
detected_format = txt

must_have:
- Python
- FastAPI
- PostgreSQL

nice_to_have:
- Redis
- Docker

match_score = 64
```

Если backend запущен на другом URL:

```powershell
$env:API_BASE_URL="http://localhost:8000/api/v1"
python .\scripts\smoke_mvp_flow.py
```

---

## 3. UTF-8-safe vacancy import diagnostic

Использовать вместо ручного PowerShell JSON, если в тексте вакансии есть кириллица.

Запуск:

```powershell
python .\scripts\import_analyze_vacancy_utf8.py
```

Ожидаемый результат:

```text
SAVED DESCRIPTION
Требования:
- Python
- FastAPI
- PostgreSQL

Будет плюсом:
- Redis
- Docker
```

И анализ:

```text
must_have:
- Python
- FastAPI
- PostgreSQL

nice_to_have:
- Redis
- Docker
```

Важно: не использовать небезопасные PowerShell heredoc/curl сценарии для кириллических JSON payload'ов. Если кириллица превратилась в `??????????`, backend должен вернуть `422`.

---

## 4. PDF extraction UTF-8 diagnostic

Проверяет, что PDF extraction, API response и DB row не содержат mojibake.

Запуск:

```powershell
python .\scripts\verify_pdf_extraction_utf8.py "C:\Users\Worker\Downloads\Резюме Перминов А.И..pdf"
```

Ожидаемые признаки:

```text
detected_format: pdf
api_text_length == db_text_length
markers: {'Ð': 0, 'Ñ': 0, 'â': 0, '�': 0}
```

Если markers не нулевые - отдельно проверять:

```text
- parser output
- raw HTTP response
- DB file_extractions.extracted_text
- способ просмотра файла/PowerShell output
```

---

## 5. Recent vacancy analysis diagnostic

Показывает последние вакансии, analysis, must-have/nice-to-have, match score и raw description.

Запуск:

```powershell
python .\scripts\list_recent_vacancy_analyses.py
```

Использовать, если:

```text
- Redis/Docker снова попали в must_have
- nice_to_have пустой
- match_score выглядит странно
- есть подозрение на corrupt input
```

Если `description_raw` выглядит так:

```text
??????????:
- Python
- FastAPI
```

это уже потерянная кириллица. Такую запись нельзя надёжно восстановить, её нужно пересоздать через UTF-8-safe import.

---

## 6. Single vacancy parser diagnostic

Проверяет, как локальный `VacancyAnalysisService` парсит конкретную запись из БД.

Запуск:

```powershell
python .\scripts\debug_vacancy_analysis_parser.py "<VACANCY_ID>"
```

Ожидаемый корректный split:

```text
must_have:
['Python', 'FastAPI', 'PostgreSQL']

nice_to_have:
['Redis', 'Docker']
```

Если local parser показывает правильно, а API/latest analysis в БД неправильный - вероятно, analysis был создан старым backend-кодом. Повторить:

```powershell
curl.exe -sS -X POST "http://localhost:8000/api/v1/vacancies/<VACANCY_ID>/analyze"
```

---

## 7. Alembic checks

Проверить состояние миграций:

```powershell
alembic heads
alembic current
alembic upgrade head
```

Текущее ожидаемое состояние:

```text
single head
current == head
```

Последний известный head:

```text
6b8d2f4a1c01
```

---

## 8. Dev DB checks

Если есть dev scripts:

```powershell
python .\scripts\dev_db_counts.py
```

Для reset dev DB:

```powershell
python .\scripts\dev_db_reset.py
```

Важно: MinIO/storage cleanup, если используется, может быть отдельным.

---

## 9. Backend start

Типовой запуск:

```powershell
python -m uvicorn app.main:app --reload
```

### Docker API container vs local uvicorn

Для локальной разработки backend обычно запускается через:

```powershell
python -m uvicorn app.main:app --reload
```

При этом Docker API-контейнер не должен занимать порт 8000.

Проверить контейнеры:

```powershell
docker ps --format "table {{.ID}}\t{{.Names}}\t{{.Ports}}"
```

Если `career-copilot-api` публикует `0.0.0.0:8000->8000/tcp`, остановить его:

```powershell
docker stop career-copilot-api
```

Postgres, Redis и MinIO оставлять запущенными.

Проверить, кто слушает порт 8000:

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen |
  Select-Object LocalAddress, LocalPort, OwningProcess
```

Проверить процесс:

```powershell
$pid8000 = (Get-NetTCPConnection -LocalPort 8000 -State Listen).OwningProcess
Get-Process -Id $pid8000 | Select-Object Id, ProcessName, Path, StartTime
Get-CimInstance Win32_Process -Filter "ProcessId=$pid8000" |
  Select-Object ProcessId, CommandLine
```

Если backend в Docker:

```powershell
docker ps
docker compose restart api
```

---

## 10. Known dev pitfalls

### PowerShell mojibake / corrupt Cyrillic JSON

Симптом:

```text
Требования
```

превращается в:

```text
РўСЂРµР±РѕРІР°РЅРёСЏ
```

или:

```text
??????????
```

Важно различать:

```text
РўСЂ... в console preview может быть display artifact.
?????????? в DB description_raw - уже потерянные данные.
```

Для вакансий с кириллицей использовать Python/httpx scripts или файл UTF-8.

### Старый backend process

Если pytest зелёный, а API ведёт себя по-старому:

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen
```

Проверить, какой процесс реально отвечает на `localhost:8000`.

### Старые analysis rows

Если vacancy analysis был создан до фикса, latest analysis может содержать старую структуру. Повторить:

```powershell
curl.exe -sS -X POST "http://localhost:8000/api/v1/vacancies/<VACANCY_ID>/analyze"
```

---

## 11. Current MVP quality gates

Перед переходом к frontend / Streamlit integration должны проходить:

```powershell
pytest -q
python .\scripts\smoke_mvp_flow.py
```

Ожидаемый статус:

```text
tests green
live smoke passed
```

Текущий known baseline:

```text
70 passed
MVP SMOKE PASSED
```
