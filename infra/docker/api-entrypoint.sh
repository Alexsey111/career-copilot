#!/bin/sh
# api-entrypoint.sh — запуск api-контейнера с автопрогоном миграций.
#
# Делает `docker compose up` самодостаточным: ждёт готовности postgres,
# прогоняет `alembic upgrade head`, затем exec'ит переданную команду
# (uvicorn в dev-compose, gunicorn в prod CMD). Миграции гоняются ровно
# один процесс (api), celery-worker/beat стартуют после service_healthy.
set -e

: "${POSTGRES_HOST:=postgres}"
: "${POSTGRES_PORT:=5432}"

echo "[entrypoint] waiting for postgres at ${POSTGRES_HOST}:${POSTGRES_PORT} ..."
i=0
while [ "$i" -lt 60 ]; do
    if python - <<'PY' 2>/dev/null
import os, psycopg
url = os.environ.get("DATABASE_URL") or os.environ.get("SYNC_DATABASE_URL") or ""
# приводим async-driver URL к sync-виду для psycopg
url = url.replace("+psycopg", "").replace("+asyncpg", "")
psycopg.connect(url, connect_timeout=3).close()
PY
    then
        echo "[entrypoint] postgres is up"
        break
    fi
    i=$((i + 1))
    echo "[entrypoint] postgres not ready ($i/60), retry in 1s..."
    sleep 1
done

if [ "$i" -ge 60 ]; then
    echo "[entrypoint] WARNING: postgres still unreachable after 60s — proceeding anyway"
fi

echo "[entrypoint] running alembic upgrade head ..."
alembic upgrade head

echo "[entrypoint] starting: $*"
exec "$@"