"""Search OpenAlex articles by keyword.

Usage:
    python search_openalex.py "graph rag"
"""

from __future__ import annotations

import argparse
import asyncio

from opentelemetry import trace

from app.clients.openalex import OpenAlexClient
from app.db.qdrant import get_qdrant_client
from app.errors import NoArticlesError
from app.repositories.vector import VectorRepository
from app.services.papers import PapersService
from app.settings import get_settings
from app.tracing import configure_tracing

tracer = trace.get_tracer(__name__)


async def main() -> None:
    settings = get_settings()
    configure_tracing(settings)

    parser = argparse.ArgumentParser(description="Search OpenAlex articles by keyword.")
    parser.add_argument("keyword", help="Keyword or phrase to search for.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum number of articles.")
    parser.add_argument(
        "--from-year",
        type=int,
        default=None,
        help="Only include articles from this publication year onward.",
    )
    args = parser.parse_args()
    openalex_client = OpenAlexClient(api_key=settings.OPENALEX_API_KEY)
    client = get_qdrant_client(url=settings.QDRANT_URL)
    repository = VectorRepository(db=client, collection_name=settings.QDRANT_COLLECTION_NAME)
    service = PapersService(openalex_client=openalex_client, vector_repository=repository)

    await search_and_insert_articles(service=service, query=args.keyword, limit=args.limit)


@tracer.start_as_current_span("cli.search_openalex")
async def search_and_insert_articles(service: PapersService, query: str, limit: int) -> None:
    try:
        articles = await service.get_articles(query=query, limit=limit)
    except NoArticlesError:
        print("No articles found")
        return

    service.insert_articles(articles=articles)


if __name__ == "__main__":
    asyncio.run(main())
