FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_CACHE_DIR=/root/.cache/pip

WORKDIR /app

RUN pip install --upgrade pip

COPY pyproject.toml build_backend.py README.md ./
# NB: --mount=type=cache (buildkit-only) убран, чтобы build проходил и с
# DOCKER_BUILDKIT=0 (legacy builder). Кеш работает через PIP_CACHE_DIR
# в volume /root/.cache/pip (см. ENV выше).
RUN pip install \
    --default-timeout=1000 \
    --retries 5 \
    --no-cache-dir \
    .[deploy]

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY gunicorn.conf.py ./

EXPOSE 7000

# Non-root runtime (ТЗ §3.5 «secure infra / non-root»).
RUN useradd --create-home --uid 1001 appuser \
    && mkdir -p /app/.local-storage \
    && chown -R appuser:appuser /app
USER appuser

CMD ["gunicorn", "app.main:app", "-c", "gunicorn.conf.py"]