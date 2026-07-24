"""dltHub jobs for starting PaperGraph ingestion."""

from __future__ import annotations

from typing import Any

import dlt
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
def ingest_openalex_from_dlthub(
    api_url: str | None = None,
    ingestion_keywords: list[str] | None = None,
    ingestion_limit: int = 10,
    ingestion_from_year: int | None = None,
    ingestion_dlt_output_dir: str = ".dlt/openalex",
    ingestion_api_token: str = "",
) -> dict[str, Any]:
    """Trigger the deployed PaperGraph API to run OpenAlex ingestion.

    Returns:
        API response containing staged and inserted record counts.
    """

    settings = build_dlthub_ingestion_settings(
        api_url=api_url,
        ingestion_keywords=ingestion_keywords,
        ingestion_limit=ingestion_limit,
        ingestion_from_year=ingestion_from_year,
        ingestion_dlt_output_dir=ingestion_dlt_output_dir,
        ingestion_api_token=ingestion_api_token,
    )
    configure_logging(settings.LOG_LEVEL)
    return trigger_openalex_ingestion_api(settings=settings)


def build_dlthub_ingestion_settings(
    api_url: str | None = None,
    ingestion_keywords: list[str] | None = None,
    ingestion_limit: int = 10,
    ingestion_from_year: int | None = None,
    ingestion_dlt_output_dir: str = ".dlt/openalex",
    ingestion_api_token: str = "",
) -> Settings:
    """Build ingestion settings from dltHub job config and optional injected values.

    Args:
        api_url: Optional API URL injected by dltHub.
        ingestion_keywords: Optional keyword list injected by dltHub.
        ingestion_limit: Optional per-keyword article limit.
        ingestion_from_year: Optional first publication year.
        ingestion_dlt_output_dir: dlt output directory used by the API.
        ingestion_api_token: Optional ingestion endpoint bearer token.

    Returns:
        Application settings scoped to the dltHub ingestion job.
    """

    job_section = "jobs.dlthub.ingest_openalex_from_dlthub"
    base_settings = get_settings()
    resolved_api_url = api_url or dlt.config.get(f"{job_section}.api_url", str)
    if not resolved_api_url:
        raise ValueError(
            "Missing dltHub config: set [jobs.dlthub.ingest_openalex_from_dlthub].api_url"
        )

    resolved_keywords = ingestion_keywords or dlt.config.get(
        f"{job_section}.ingestion_keywords",
        list,
    )
    resolved_limit = dlt.config.get(f"{job_section}.ingestion_limit", int) or ingestion_limit
    resolved_from_year = (
        dlt.config.get(f"{job_section}.ingestion_from_year", int) or ingestion_from_year
    )
    resolved_output_dir = (
        dlt.config.get(f"{job_section}.ingestion_dlt_output_dir", str) or ingestion_dlt_output_dir
    )
    resolved_token = (
        ingestion_api_token
        or dlt.secrets.get(f"{job_section}.ingestion_api_token", str)
        or dlt.config.get(f"{job_section}.ingestion_api_token", str)
    )

    return Settings(
        API_URL=resolved_api_url,
        INGESTION_KEYWORD=base_settings.INGESTION_KEYWORD,
        INGESTION_KEYWORDS=resolved_keywords or base_settings.INGESTION_KEYWORDS,
        INGESTION_LIMIT=resolved_limit,
        INGESTION_FROM_YEAR=resolved_from_year,
        INGESTION_DLT_OUTPUT_DIR=resolved_output_dir,
        INGESTION_API_TOKEN=resolved_token or "",
    )


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
