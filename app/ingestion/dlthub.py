"""dltHub jobs for starting PaperGraph ingestion."""

from __future__ import annotations

from typing import Any

import httpx
from dlt.hub import run

from app.logging import configure_logging
from app.settings import Settings, get_settings


@run.job(
    name="ingest_openalex_from_dlthub",
    execute={"timeout": {"timeout": 1800}},
    expose={
        "display_name": "Ingest OpenAlex papers",
        "tags": ["papergraph", "openalex", "ingestion"],
    },
)
def ingest_openalex_from_dlthub() -> dict[str, Any]:
    """Trigger the deployed PaperGraph API to run OpenAlex ingestion.

    Returns:
        API response containing staged and inserted record counts.
    """

    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)
    return trigger_openalex_ingestion_api(settings=settings)


def trigger_openalex_ingestion_api(settings: Settings) -> dict[str, Any]:
    """Call the PaperGraph API ingestion endpoint for configured keywords.

    Args:
        settings: Application settings containing API URL and ingestion defaults.

    Returns:
        Summary with one API response per configured keyword.

    Raises:
        httpx.HTTPStatusError: If the API rejects or fails the request.
    """

    headers = {}
    if settings.INGESTION_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.INGESTION_API_TOKEN}"

    results = []
    with httpx.Client(timeout=600) as client:
        for keyword in ingestion_keywords(settings):
            payload = build_ingestion_payload(settings=settings, keyword=keyword)
            response = client.post(
                f"{settings.API_URL.rstrip('/')}/ingestions/openalex",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            results.append(response.json())

    return {
        "keyword_count": len(results),
        "staged_records": sum(int(result.get("staged_records", 0)) for result in results),
        "inserted_articles": sum(int(result.get("inserted_articles", 0)) for result in results),
        "results": results,
    }


def ingestion_keywords(settings: Settings) -> list[str]:
    """Resolve configured ingestion keywords.

    Args:
        settings: Application settings containing list and single keyword values.

    Returns:
        Non-empty keyword list. `INGESTION_KEYWORDS` wins over the legacy single keyword.
    """

    keywords = settings.INGESTION_KEYWORDS or [settings.INGESTION_KEYWORD]
    return [keyword.strip() for keyword in keywords if keyword.strip()]


def build_ingestion_payload(settings: Settings, keyword: str) -> dict[str, Any]:
    """Build the API request payload for one keyword.

    Args:
        settings: Ingestion settings shared across all keywords.
        keyword: OpenAlex search query.

    Returns:
        JSON payload for `POST /ingestions/openalex`.
    """

    payload: dict[str, Any] = {
        "keyword": keyword,
        "limit": settings.INGESTION_LIMIT,
        "dlt_output_dir": settings.INGESTION_DLT_OUTPUT_DIR,
    }
    if settings.INGESTION_FROM_YEAR is not None:
        payload["from_year"] = settings.INGESTION_FROM_YEAR
    return payload
