PYTHON_TARGETS = app migrations tests

.PHONY: check lint format-check typecheck test fix format

check: lint format-check typecheck test

lint:
	uv run ruff check $(PYTHON_TARGETS)

format-check:
	uv run ruff format --check $(PYTHON_TARGETS)

typecheck:
	uv run ty check $(PYTHON_TARGETS)

test:
	uv run pytest -q

fix:
	uv run ruff check $(PYTHON_TARGETS) --fix
	uv run ruff format $(PYTHON_TARGETS)
