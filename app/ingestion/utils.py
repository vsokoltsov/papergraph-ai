import json
from pathlib import Path
from typing import Any

from app.clients.openalex import OpenAlexArticle


def build_openalex_filters(from_year: int | None = None) -> list[str]:
    """Build OpenAlex filter expressions for article ingestion.

    Args:
        from_year: Optional first publication year to include.

    Returns:
        OpenAlex filter expressions accepted by the works API.
    """

    filters = ["type:article"]
    if from_year:
        filters.append(f"from_publication_date:{from_year}-01-01")
    return filters


def openalex_records_to_articles(records: list[dict[str, Any]]) -> list[OpenAlexArticle]:
    """Validate raw OpenAlex records as application article models.

    Args:
        records: Raw JSON objects returned by the OpenAlex works API.

    Returns:
        Parsed OpenAlex article models.
    """

    return [OpenAlexArticle.model_validate(record) for record in records]


def compact_openalex_records_for_dlt(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert raw OpenAlex records to a shallow dlt staging shape.

    Args:
        records: Raw JSON objects returned by the OpenAlex works API.

    Returns:
        Records with stable scalar columns and the full raw payload as JSON text.
    """

    compact_records = []
    for record in records:
        compact_records.append(
            {
                "id": record.get("id"),
                "doi": record.get("doi"),
                "title": record.get("title") or record.get("display_name"),
                "publication_year": record.get("publication_year"),
                "publication_date": record.get("publication_date"),
                "type": record.get("type"),
                "raw_payload": json.dumps(record, sort_keys=True),
            }
        )
    return compact_records


def resolve_output_dir(output_dir: str) -> str:
    """Resolve a dlt output directory to an absolute filesystem path.

    Args:
        output_dir: Relative or absolute output directory.

    Returns:
        Absolute path as a string.
    """

    return str(Path(output_dir).resolve())
