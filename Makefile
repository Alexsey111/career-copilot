.PHONY: demo demo-reset demo-seed demo-check backend streamlit

PYTHON ?= python

demo-reset:
	$(PYTHON) scripts/reset_demo_environment.py

demo-seed:
	$(PYTHON) scripts/seed_demo.py

demo-check:
	$(PYTHON) scripts/check_demo_trust_states.py

backend:
	$(PYTHON) -m uvicorn app.main:app --host 0.0.0.0 --port 8000

streamlit:
	$(PYTHON) -m streamlit run frontend/streamlit/app.py

demo: demo-reset
	@echo "Demo environment is ready."
	@echo "Start the backend with: make backend"
	@echo "Start Streamlit with: make streamlit"
