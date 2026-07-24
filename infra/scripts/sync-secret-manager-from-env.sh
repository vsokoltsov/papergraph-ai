#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${1:-${GCP_PROJECT_ID:-papergraph-ai}}"
ENV_FILE="${2:-.env}"

required_keys=(
  OPENALEX_API_KEY
  OPENAI_API_KEY
  NEO4J_USER
  NEO4J_PASSWORD
)

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Env file not found: $ENV_FILE" >&2
  exit 1
fi

read_env_value() {
  local key="$1"

  awk -F= -v key="$key" '
    $1 == key {
      sub(/^[^=]*=/, "")
      gsub(/^"|"$/, "")
      gsub(/^'\''|'\''$/, "")
      print
    }
  ' "$ENV_FILE" | tail -n 1
}

resolve_value() {
  local key="$1"
  local value

  value="$(read_env_value "$key")"

  printf "%s" "$value"
}

for key in "${required_keys[@]}"; do
  value="$(resolve_value "$key")"

  if [[ -z "$value" ]]; then
    echo "Skipping missing or empty key: $key" >&2
    continue
  fi

  printf "%s" "$value" | gcloud secrets versions add "$key" \
    --project "$PROJECT_ID" \
    --data-file=-
  echo "Synced $key"
done
