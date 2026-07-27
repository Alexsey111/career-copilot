.PHONY: demo demo-reset demo-seed demo-check local-health local-start backend streamlit test test-contracts \
        docker-build docker-up docker-down docker-logs docker-ps docker-migrate docker-smoke docker-reset

PYTHON ?= python
# Compose-файл и legacy-builder обход (DNS-проблема buildkit на этой машине,
# см. memory docker-build-fpdf2-dns-issue). Build — обязательно с обоими env.
COMPOSE := docker compose -f infra/docker/docker-compose.yml
BUILD_ENV := DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0

demo-reset:
	$(PYTHON) scripts/reset_demo_environment.py

demo-seed:
	$(PYTHON) scripts/seed_demo.py

demo-check:
	$(PYTHON) scripts/check_demo_trust_states.py

local-health:
	$(PYTHON) scripts/check_local_health.py

local-start:
	docker compose -f infra/docker/docker-compose.yml up -d --build api postgres redis minio
	$(PYTHON) scripts/check_local_health.py

backend:
	$(PYTHON) -m uvicorn app.main:app --host 0.0.0.0 --port 7000

streamlit:
	$(PYTHON) scripts/start_streamlit.py

test:
	$(PYTHON) -m pytest -q

test-contracts:
	$(PYTHON) -m pytest -q \
		tests/test_api_contract_snapshots.py \
		tests/test_api_error_contract.py \
		tests/test_error_contract_hardening.py \
		tests/test_health_diagnostics.py

demo: demo-reset
	@echo "Demo environment is ready."
	@echo "Start the backend with: make backend"
	@echo "Start Streamlit with: make streamlit"

# --- Docker-стенд (infra/docker/docker-compose.yml) ---
# api-контейнер прогоняет миграции через entrypoint, поэтому `make docker-up`
# сразу даёт рабочий стенд. Доп. команды — для ручного контроля.

docker-build:
	$(BUILD_ENV) $(COMPOSE) build api

# Поднять весь стек; миграции гонятся api-entrypoint.sh автоматически.
docker-up:
	$(COMPOSE) up -d
	@echo "Waiting for api health..."
	@$(COMPOSE) exec api sh -c 'for i in 1 2 3 4 5 6 7 8 9 10; do python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen(\"http://localhost:7000/health\",timeout=3).status==200 else 1)" 2>/dev/null && { echo "api is healthy"; exit 0; }; sleep 3; done; echo "api not healthy yet — see make docker-logs"; exit 1' || true

docker-down:
	$(COMPOSE) down

docker-logs:
	$(COMPOSE) logs -f --tail=100

docker-ps:
	$(COMPOSE) ps

# Ручной прогон миграций (на случай, если нужно без рестарта).
docker-migrate:
	$(COMPOSE) exec api alembic upgrade head

# End-to-end smoke #1/#2 (см. tools/smoke_e2e.py).
docker-smoke:
	$(PYTHON) tools/smoke_e2e.py

# Полный сброс: удалить контейнеры + тома (БД, MinIO, метрики) и поднять заново.
docker-reset:
	$(COMPOSE) down -v
	$(COMPOSE) up -d
