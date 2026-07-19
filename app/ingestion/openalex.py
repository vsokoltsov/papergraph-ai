from __future__ import annotations

from pathlib import Path
from time import monotonic
from typing import Any

import dlt
import httpx

from app.ingestion.models import OpenAlexIngestionResult
from app.ingestion.protocols import PaperInserter
from app.ingestion.utils import (
    build_openalex_filters,
    compact_openalex_records_for_dlt,
    openalex_records_to_articles,
    resolve_output_dir,
)
from app.metrics import (
    DLT_RECORDS_STAGED_TOTAL,
    INGESTION_RUN_DURATION_SECONDS,
    INGESTION_RUNS_TOTAL,
    OPENALEX_ARTICLES_TOTAL,
)

OPENALEX_WORKS_URL = "https://api.openalex.org/works"
DEFAULT_DLT_OUTPUT_DIR = ".dlt/openalex"


@dlt.resource(
    name="openalex_articles",
    table_name="openalex_articles",
    write_disposition="replace",
    primary_key="id",
)
def openalex_articles_resource(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Create a dlt resource for compact OpenAlex article records.

    Args:
        records: Raw OpenAlex work records.

    Returns:
        Compact records with stable scalar columns and raw payload text.
    """

    return compact_openalex_records_for_dlt(records)


@dlt.source(name="papergraph_openalex")
def openalex_source(records: list[dict[str, Any]]) -> Any:
    """Create the dlt source used to stage OpenAlex records.

    Args:
        records: Raw OpenAlex work records.

    Returns:
        dlt source containing the OpenAlex article resource.
    """

    return openalex_articles_resource(records)


def fetch_openalex_article_records(
    query: str,
    limit: int,
    api_key: str,
    from_year: int | None = None,
) -> list[dict[str, Any]]:
    """Fetch raw article records from the OpenAlex works API.

    Args:
        query: Keyword or phrase to search for.
        limit: Maximum number of records to fetch.
        api_key: OpenAlex API key.
        from_year: Optional first publication year to include.

    Returns:
        Raw OpenAlex work records.

    Raises:
        httpx.HTTPStatusError: If OpenAlex returns an unsuccessful HTTP status.
    """

    filters = build_openalex_filters(from_year=from_year)
    with httpx.Client(timeout=20) as client:
        response = client.get(
            OPENALEX_WORKS_URL,
            params={
                "api_key": api_key,
                "search": query,
                "filter": ",".join(filters),
                "per-page": limit,
            },
        )
    response.raise_for_status()
    return list(response.json()["results"])


def stage_openalex_article_records(
    records: list[dict[str, Any]],
    output_dir: str = DEFAULT_DLT_OUTPUT_DIR,
) -> Any:
    """Stage raw OpenAlex records with dlt.

    Args:
        records: Raw OpenAlex work records.
        output_dir: Local directory for the dlt filesystem destination.

    Returns:
        dlt load metadata returned by `pipeline.run`.
    """

    output_path = Path(output_dir).resolve()
    pipeline = dlt.pipeline(
        pipeline_name="papergraph_openalex",
        destination=dlt.destinations.filesystem(bucket_url=f"file://{output_path}"),
        dataset_name="openalex",
    )
    return pipeline.run(
        openalex_source(records),
        loader_file_format="jsonl",
    )


async def ingest_openalex_articles(
    service: PaperInserter,
    query: str,
    limit: int,
    api_key: str,
    dlt_output_dir: str = DEFAULT_DLT_OUTPUT_DIR,
    from_year: int | None = None,
) -> OpenAlexIngestionResult:
    """Run OpenAlex ingestion through dlt staging and app persistence.

    Args:
        service: Service capable of inserting parsed articles.
        query: Keyword or phrase to search for.
        limit: Maximum number of records to ingest.
        api_key: OpenAlex API key.
        dlt_output_dir: Local dlt filesystem destination directory.
        from_year: Optional first publication year to include.

    Returns:
        Summary of staged and inserted records.
    """

    started_at = monotonic()
    try:
        records = fetch_openalex_article_records(
            query=query,
            limit=limit,
            api_key=api_key,
            from_year=from_year,
        )
        OPENALEX_ARTICLES_TOTAL.inc(len(records))
        load_info = stage_openalex_article_records(records=records, output_dir=dlt_output_dir)
        DLT_RECORDS_STAGED_TOTAL.inc(len(records))
        articles = openalex_records_to_articles(records)
        await service.insert_articles(articles=articles)
        INGESTION_RUNS_TOTAL.labels(status="success").inc()

        return OpenAlexIngestionResult(
            query=query,
            staged_records=len(records),
            inserted_articles=len(articles),
            dlt_output_dir=resolve_output_dir(dlt_output_dir),
            dlt_load_info=str(load_info),
        )
    except Exception:
        INGESTION_RUNS_TOTAL.labels(status="error").inc()
        raise
    finally:
        INGESTION_RUN_DURATION_SECONDS.observe(monotonic() - started_at)
