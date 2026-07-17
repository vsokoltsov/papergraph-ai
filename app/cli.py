"""Search OpenAlex articles by keyword.

Usage:
    python search_openalex.py "graph rag"
"""

from __future__ import annotations
import asyncio

import argparse
from app.settings import get_settings
from app.clients.openalex import OpenAlexClient
from app.db.qdrant  import get_qdrant_client
from app.repositories.vector import VectorRepository
from app.services.papers import PapersService
from app.errors import NoArticlesError


async def main() -> None:
    settings = get_settings()

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
    openalex_client = OpenAlexClient(
        api_key=settings.OPENALEX_API_KEY
    )
    client = get_qdrant_client(url=settings.QDRANT_URL)
    repository = VectorRepository(
        db=client,
        collection_name=settings.QDRANT_COLLECTION_NAME
    )
    service = PapersService(
        openalex_client=openalex_client,
        vector_repository=repository
    )
    try:
        articles = await service.get_articles(query=args.keyword, limit=args.limit)
    except NoArticlesError:
        print("No articles found")
        return

    service.insert_articles(articles=articles)


if __name__ == "__main__":
    asyncio.run(main())
