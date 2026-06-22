.PHONY: demo demo-reset demo-seed demo-check local-health local-start backend streamlit test test-contracts

PYTHON ?= python

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
