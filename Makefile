PYTHON_TARGETS = app migrations tests

.PHONY: check lint format-check typecheck test dashboards ingest-openalex eval-services eval-retrieval eval-llm generate-llm-ground-truth backend ui mcp terraform-fmt helm-template helm-template-dev sync-gcp-secrets fix format

check: lint format-check typecheck test

lint:
	uv run ruff check $(PYTHON_TARGETS)

format-check:
	uv run ruff format --check $(PYTHON_TARGETS)

typecheck:
	uv run ty check $(PYTHON_TARGETS)

test:
	uv run pytest -q --cov=app --cov-report=term --cov-report=xml

dashboards:
	uv run python -m app.dashboards.generate

ingest-openalex:
	uv run python -m app.ingestion.run "$(query)"

eval-services:
	docker compose up -d qdrant neo4j pushgateway prometheus grafana

eval-retrieval:
	uv run python -m app.eval.retrieval.evaluate

eval-llm: eval-services
	uv run python -m app.eval.llm.evaluate

generate-llm-ground-truth:
	uv run python -m app.eval.llm.ground_truth.evaluate

backend:
	uv run uvicorn app.api:app --reload

ui:
	uv run streamlit run app/ui.py

mcp:
	uv run python -m app.mcp

terraform-fmt:
	terraform -chdir=infra/terraform fmt -recursive

helm-template:
	helm template papergraph-ai infra/helm/papergraph

helm-template-dev:
	helm template papergraph-ai infra/helm/papergraph --values infra/helm/papergraph/values-dev.yaml

sync-gcp-secrets:
	bash infra/scripts/sync-secret-manager-from-env.sh

fix:
	uv run ruff check $(PYTHON_TARGETS) --fix
	uv run ruff format $(PYTHON_TARGETS)
