from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol

Retriever = Callable[[str, int], Awaitable[list[str]]]


class ArticleSearchClient(Protocol):
    """Client interface for keyword search against a paper source."""

    async def get_articles(self, query: str, limit: int = 20) -> list[Any]: ...


class VectorSearchRepository(Protocol):
    """Repository interface for vector-based paper search."""

    async def search_papers(
        self,
        query: str | list[float],
        limit: int = 5,
    ) -> list[dict[str, Any]]: ...


class GraphSearchRepository(Protocol):
    """Repository interface for graph-based paper search and graph expansion."""

    async def search_papers(self, query: str, limit: int = 5) -> list[dict]: ...

    async def get_paper_context(self, openalex_ids: list[str]) -> list[dict]: ...
