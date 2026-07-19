from __future__ import annotations

import argparse
import asyncio

from app.clients.openalex import OpenAlexClient
from app.db.neo4j import get_neo4j_driver
from app.db.qdrant import get_qdrant_client
from app.ingestion.openalex import DEFAULT_DLT_OUTPUT_DIR, ingest_openalex_articles
from app.logging import configure_logging
from app.metrics import push_metrics_to_gateway
from app.repositories.graph import GraphRepository
from app.repositories.vector import VectorRepository
from app.services.papers import PapersService
from app.settings import get_settings
from app.tracing import configure_tracing


async def main() -> None:
    """Run the OpenAlex ingestion CLI."""

    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)
    configure_tracing(settings)

    parser = build_parser()
    args = parser.parse_args()

    service = build_papers_service()
    result = await ingest_openalex_articles(
        service=service,
        query=args.keyword,
        limit=args.limit,
        api_key=settings.OPENALEX_API_KEY,
        dlt_output_dir=args.dlt_output_dir,
        from_year=args.from_year,
    )
    print(f"Staged {result.staged_records} OpenAlex record(s) in {result.dlt_output_dir}")
    print(f"Inserted {result.inserted_articles} article(s) into vector and graph stores")
    push_ingestion_metrics(settings.PROMETHEUS_PUSHGATEWAY_URL)


def build_parser() -> argparse.ArgumentParser:
    """Build the ingestion command-line argument parser.

    Returns:
        Configured argument parser for the ingestion CLI.
    """

    parser = argparse.ArgumentParser(description="Ingest OpenAlex articles with dlt staging.")
    parser.add_argument("keyword", help="Keyword or phrase to search for.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum number of articles.")
    parser.add_argument(
        "--from-year",
        type=int,
        default=None,
        help="Only include articles from this publication year onward.",
    )
    parser.add_argument(
        "--dlt-output-dir",
        default=DEFAULT_DLT_OUTPUT_DIR,
        help="Local directory where dlt stores staged OpenAlex records.",
    )
    return parser


def build_papers_service() -> PapersService:
    """Build the paper service used by ingestion.

    Returns:
        Paper service configured with OpenAlex, Qdrant, and Neo4j clients.
    """

    settings = get_settings()
    qdrant_db = get_qdrant_client(url=settings.QDRANT_URL)
    neo4j_db = get_neo4j_driver(
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD,
    )
    return PapersService(
        openalex_client=OpenAlexClient(api_key=settings.OPENALEX_API_KEY),
        vector_repository=VectorRepository(
            db=qdrant_db,
            collection_name=settings.QDRANT_COLLECTION_NAME,
        ),
        graph_repository=GraphRepository(db=neo4j_db),
    )


def push_ingestion_metrics(gateway_url: str) -> None:
    """Push ingestion metrics for the short-lived CLI process.

    Args:
        gateway_url: Pushgateway URL scraped by Prometheus.
    """

    try:
        push_metrics_to_gateway(gateway_url=gateway_url, job="papergraph-ingestion")
    except Exception as error:
        print(f"Could not push Prometheus metrics: {error}")


if __name__ == "__main__":
    asyncio.run(main())
