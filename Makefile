PYTHON_TARGETS = app migrations tests

.PHONY: check lint format-check typecheck test backend ui fix format

check: lint format-check typecheck test

lint:
	uv run ruff check $(PYTHON_TARGETS)

format-check:
	uv run ruff format --check $(PYTHON_TARGETS)

typecheck:
	uv run ty check $(PYTHON_TARGETS)

test:
	uv run pytest -q --cov=app --cov-report=term --cov-report=xml

backend:
	uv run uvicorn app.api:app --reload

ui:
	uv run streamlit run app/ui.py

fix:
	uv run ruff check $(PYTHON_TARGETS) --fix
	uv run ruff format $(PYTHON_TARGETS)
