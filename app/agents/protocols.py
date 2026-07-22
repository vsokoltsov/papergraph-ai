"""Protocols used by the PaperGraph research agent."""

from typing import Any, Protocol

from app.clients.openalex import OpenAlexArticle


class PapersServiceClient(Protocol):
    """Protocol for paper source and ingestion operations."""

    async def get_articles(self, query: str, limit: int = 20) -> list[OpenAlexArticle]:
        """Return OpenAlex articles matching a search query.

        Args:
            query: Keyword or phrase used for search.
            limit: Maximum number of articles to return.

        Returns:
            Matching OpenAlex article objects.
        """

        ...

    async def insert_articles(self, articles: list[OpenAlexArticle]) -> None:
        """Insert articles into downstream storage.

        Args:
            articles: Articles to insert.
        """

        ...


class PaperVectorRepository(Protocol):
    """Protocol for semantic paper retrieval."""

    async def search_papers(
        self,
        query: str | list[float],
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Search papers by text or vector query.

        Args:
            query: Text query or embedding vector.
            limit: Maximum number of papers to return.

        Returns:
            Retrieved paper payload dictionaries.
        """

        ...


class PaperGraphRepository(Protocol):
    """Protocol for graph metadata retrieval."""

    async def search_papers(self, query: str, limit: int = 5) -> list[dict]:
        """Search graph paper metadata.

        Args:
            query: Keyword query.
            limit: Maximum number of papers to return.

        Returns:
            Retrieved graph paper rows.
        """

        ...

    async def get_paper_context(self, openalex_ids: list[str]) -> list[dict]:
        """Return graph context for OpenAlex paper IDs.

        Args:
            openalex_ids: OpenAlex paper IDs to enrich.

        Returns:
            Graph context rows for the provided paper IDs.
        """

        ...
