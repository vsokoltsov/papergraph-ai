"""dltHub jobs for starting PaperGraph ingestion."""

from __future__ import annotations

from typing import Any

import httpx
from dlt.hub import run

from app.logging import configure_logging
from app.settings import Settings, get_settings


@run.job(
    name="ingest_openalex_from_dlthub",
    execute={"timeout": "30m"},
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
    """Call the PaperGraph API ingestion endpoint.

    Args:
        settings: Application settings containing API URL and ingestion defaults.

    Returns:
        Parsed JSON response from the API.

    Raises:
        httpx.HTTPStatusError: If the API rejects or fails the request.
    """

    headers = {}
    if settings.INGESTION_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.INGESTION_API_TOKEN}"

    payload: dict[str, Any] = {
        "keyword": settings.INGESTION_KEYWORD,
        "limit": settings.INGESTION_LIMIT,
        "dlt_output_dir": settings.INGESTION_DLT_OUTPUT_DIR,
    }
    if settings.INGESTION_FROM_YEAR is not None:
        payload["from_year"] = settings.INGESTION_FROM_YEAR

    with httpx.Client(timeout=600) as client:
        response = client.post(
            f"{settings.API_URL.rstrip('/')}/ingestions/openalex",
            json=payload,
            headers=headers,
        )
    response.raise_for_status()
    return dict(response.json())
