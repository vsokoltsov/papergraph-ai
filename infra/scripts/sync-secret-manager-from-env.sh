#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${1:-${GCP_PROJECT_ID:-papergraph-ai}}"
ENV_FILE="${2:-.env}"

required_keys=(
  OPENALEX_API_KEY
  OPENAI_API_KEY
  QDRANT_URL
  NEO4J_URI
  NEO4J_USER
  NEO4J_PASSWORD
  POSTGRES_PASSWORD
  PAPERGRAPH_API_URL
  LOGFIRE_TOKEN
)

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Env file not found: $ENV_FILE" >&2
  exit 1
fi

for key in "${required_keys[@]}"; do
  value="$(
    awk -F= -v key="$key" '
      $1 == key {
        sub(/^[^=]*=/, "")
        print
      }
    ' "$ENV_FILE" | tail -n 1
  )"

  if [[ -z "$value" ]]; then
    echo "Skipping missing or empty key: $key" >&2
    continue
  fi

  printf "%s" "$value" | gcloud secrets versions add "$key" \
    --project "$PROJECT_ID" \
    --data-file=-
  echo "Synced $key"
done
