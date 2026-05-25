# Локальная operational routine: сброс и старт с нуля

Эта процедура нужна, когда нужно быстро очистить локальную среду и начать заново:

1. очистить PostgreSQL;
2. убедиться, что таблицы пустые;
3. очистить bucket в MinIO;
4. поднять local stack;
5. прогнать smoke flow.

Если нужен deterministic reset для demo-последовательности, используйте:

```powershell
python scripts/reset_demo_environment.py
```

Для one-click local startup доступны цели:

```powershell
make local-start
make local-health
make backend
make streamlit
```

## Test execution

Правило для локального и CI-запуска тестов:

- полный test suite запускать sequentially против shared PostgreSQL test DB;
- parallel runs допустимы только при использовании отдельной isolated DB per worker;
- если тесты используют общий PostgreSQL test DB, не включайте parallel execution по умолчанию.

Для быстрых проверок доступны цели:

```powershell
make test
make test-contracts
```

## 1. Очистить БД

Если `psycopg` уже установлен в текущем `.venv`, можно выполнить очистку прямо из PowerShell:

```powershell
@'
import psycopg

conn = psycopg.connect("postgresql://career_user:career_pass@localhost:5432/career_copilot")
conn.autocommit = True
cur = conn.cursor()
cur.execute("TRUNCATE TABLE users CASCADE;")
print("TRUNCATE users CASCADE done")
cur.close()
conn.close()
'@ | python -
```

## 2. Проверить, что данные пустые

```powershell
@'
import psycopg

tables = ["users", "source_files", "vacancies", "application_records"]
conn = psycopg.connect("postgresql://career_user:career_pass@localhost:5432/career_copilot")
cur = conn.cursor()

for table in tables:
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    print(table, cur.fetchone()[0])

cur.close()
conn.close()
'@ | python -
```

## 3. Очистить MinIO bucket

Проще всего выполнить это через временный контейнер `minio/mc`, без установки `mc` на Windows.

```powershell
docker run --rm -e MC_HOST_local=http://minioadmin:minioadmin@host.docker.internal:9000 minio/mc rm --recursive --force local/career-copilot
```

Если нужен явный `alias set`, то можно так:

```powershell
docker run --rm minio/mc alias set local http://host.docker.internal:9000 minioadmin minioadmin
docker run --rm minio/mc rm --recursive --force local/career-copilot
```

## 4. Поднять backend

Для локального старта используйте:

```powershell
make local-start
```

Если нужно только повторно проверить состояние без нового запуска:

```powershell
make local-health
```

## 5. Smoke flow

Минимальный smoke flow:

1. `GET /health` должен вернуть `{"status":"ok"}`;
2. затем прогнать один базовый сценарий через API, который для вас является стартовым;
3. после smoke проверить, что в БД появились ожидаемые записи и в MinIO появился bucket/объекты.

Пример проверки health:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

Если нужен более формальный smoke, можно заменить ручной шаг на тесты:

```powershell
python -m pytest
```

## Примечания

- Команды выше рассчитаны на локальный запуск из корня репозитория.
- Если `psycopg` не установлен в `.venv`, сначала поставьте зависимости проекта.
- Имя bucket сейчас берётся из настройки `MINIO_BUCKET`; по умолчанию это `career-copilot`.
- HH import зависит от доступности внешнего HH API и может вернуть `403`/`502`.
- Ручной импорт вакансии остаётся надёжным fallback-путём для MVP.
