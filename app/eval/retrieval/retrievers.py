from __future__ import annotations

import httpx

from app.eval.retrieval.ids import normalize_openalex_id
from app.eval.retrieval.protocols import (
    ArticleSearchClient,
    GraphSearchRepository,
    Retriever,
    VectorSearchRepository,
)


def openalex_keyword_retriever(client: ArticleSearchClient) -> Retriever:
    """Create a retriever that uses OpenAlex keyword search.

    Args:
        client: OpenAlex API client.

    Returns:
        Async retriever function.
    """

    async def retrieve(question: str, k: int) -> list[str]:
        """Retrieve OpenAlex IDs from OpenAlex keyword search."""

        try:
            articles = await client.get_articles(query=question, limit=k)
        except httpx.HTTPError:
            return []

        return [normalize_openalex_id(article.id) for article in articles]

    return retrieve


def qdrant_vector_retriever(repository: VectorSearchRepository) -> Retriever:
    """Create a retriever that uses Qdrant vector search.

    Args:
        repository: Vector repository with a search method.

    Returns:
        Async retriever function.
    """

    async def retrieve(question: str, k: int) -> list[str]:
        """Retrieve OpenAlex IDs from Qdrant payloads."""

        results = await repository.search_papers(query=question, limit=k)
        return [
            normalize_openalex_id(result["payload"]["openalex_id"])
            for result in results
            if result.get("payload", {}).get("openalex_id")
        ]

    return retrieve


def graph_keyword_retriever(repository: GraphSearchRepository) -> Retriever:
    """Create a retriever that uses Neo4j keyword search over graph metadata.

    Args:
        repository: Graph repository with a search method.

    Returns:
        Async retriever function.
    """

    async def retrieve(question: str, k: int) -> list[str]:
        """Retrieve OpenAlex IDs from graph search results."""

        results = await repository.search_papers(query=question, limit=k)
        return [
            normalize_openalex_id(result["paper"]["openalex_id"])
            for result in results
            if result.get("paper", {}).get("openalex_id")
        ]

    return retrieve


def qdrant_vector_plus_graph_retriever(
    vector_repository: VectorSearchRepository,
    graph_repository: GraphSearchRepository,
) -> Retriever:
    """Create a retriever that combines vector search with graph expansion.

    The approach starts from Qdrant vector hits, then adds cited papers from Neo4j
    graph context. This is the selected production retrieval strategy.

    Args:
        vector_repository: Vector repository used for initial semantic search.
        graph_repository: Graph repository used for citation expansion.

    Returns:
        Async retriever function.
    """

    async def retrieve(question: str, k: int) -> list[str]:
        """Retrieve OpenAlex IDs from vector hits plus graph references."""

        vector_results = await qdrant_vector_retriever(vector_repository)(question, k)
        graph_context = await graph_repository.get_paper_context(vector_results)

        ids = list(vector_results)
        for context in graph_context:
            for reference in context.get("references", []):
                openalex_id = reference.get("openalex_id")
                if openalex_id and normalize_openalex_id(openalex_id) not in ids:
                    ids.append(normalize_openalex_id(openalex_id))

        return ids[:k]

    return retrieve
