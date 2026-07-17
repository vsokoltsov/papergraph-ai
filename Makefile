PYTHON_TARGETS = app migrations

.PHONY: check lint format-check typecheck fix format

check: lint format-check typecheck

lint:
	uv run ruff check $(PYTHON_TARGETS)

format-check:
	uv run ruff format --check $(PYTHON_TARGETS)

typecheck:
	uv run ty check $(PYTHON_TARGETS)

fix:
	uv run ruff check $(PYTHON_TARGETS) --fix
	uv run ruff format $(PYTHON_TARGETS)

