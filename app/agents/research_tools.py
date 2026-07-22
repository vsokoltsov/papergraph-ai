"""LangChain tool functions used by the PaperGraph research agent."""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import structlog

from app.agents.constants import QUERY_STOPWORDS
from app.agents.models import AgentEvent
from app.agents.protocols import PaperGraphRepository, PapersServiceClient, PaperVectorRepository
from app.clients.openalex import OpenAlexArticle
from app.metrics import record_agent_tool_results, track_agent_tool

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ResearchToolRuntime:
    """Runtime dependency container for research tools.

    Attributes:
        papers_service: Service used for OpenAlex fetch and ingestion.
        vector_repository: Repository used for vector search.
        graph_repository: Repository used for graph search and context lookup.
        emit_event: Optional callback for streaming structured tool events.
    """

    papers_service: PapersServiceClient
    vector_repository: PaperVectorRepository
    graph_repository: PaperGraphRepository
    emit_event: Callable[[AgentEvent], None] | None = None

    async def rewrite_search_query(self, question: str) -> str:
        """Rewrite a natural-language question into a compact retrieval query.

        Args:
            question: Natural-language user question.

        Returns:
            Rewritten retrieval query.
        """

        return await rewrite_search_query_tool(question, emit_event=self.emit_event)

    async def search_openalex(self, query: str, limit: int = 5) -> str:
        """Search OpenAlex for papers and return short metadata previews.

        Args:
            query: Keyword or phrase to search.
            limit: Maximum number of articles to return.

        Returns:
            JSON list of compact article previews.
        """

        return await search_openalex(
            query,
            limit,
            papers_service=self.papers_service,
            emit_event=self.emit_event,
        )

    async def ingest_papers(self, query: str, limit: int = 5) -> str:
        """Search OpenAlex and store matching papers.

        Args:
            query: Keyword or phrase to search.
            limit: Maximum number of articles to ingest.

        Returns:
            JSON object with insertion count and article previews.
        """

        return await ingest_papers(
            query,
            limit,
            papers_service=self.papers_service,
            emit_event=self.emit_event,
        )

    async def search_vector_database(self, query: str, limit: int = 5) -> str:
        """Search stored paper titles and abstracts in the vector database.

        Args:
            query: Retrieval query.
            limit: Maximum number of papers to return.

        Returns:
            JSON list of retrieved vector-search results.
        """

        return await search_vector_database(
            query,
            limit,
            vector_repository=self.vector_repository,
            emit_event=self.emit_event,
        )

    async def search_graph_database(self, query: str, limit: int = 5) -> str:
        """Search stored paper metadata, topics, and sources.

        Args:
            query: Retrieval query.
            limit: Maximum number of papers to return.

        Returns:
            JSON list of graph-search results.
        """

        return await search_graph_database(
            query,
            limit,
            graph_repository=self.graph_repository,
            emit_event=self.emit_event,
        )

    async def get_graph_context(self, openalex_ids: list[str]) -> str:
        """Get graph context for OpenAlex paper IDs from Neo4j.

        Args:
            openalex_ids: OpenAlex paper IDs to enrich.

        Returns:
            JSON list of graph context rows.
        """

        return await get_graph_context(
            openalex_ids,
            graph_repository=self.graph_repository,
            emit_event=self.emit_event,
        )

    async def rerank_documents(self, question: str, documents_json: str, limit: int = 5) -> str:
        """Rerank retrieved documents for the original user question.

        Args:
            question: Original user question.
            documents_json: JSON list of retrieved documents.
            limit: Maximum number of documents to return.

        Returns:
            JSON list of reranked documents.
        """

        return await rerank_documents_tool(
            question,
            documents_json,
            limit,
            emit_event=self.emit_event,
        )


def to_json(data: Any) -> str:
    """Serialize data to JSON for tool responses.

    Args:
        data: JSON-compatible data to serialize.

    Returns:
        Serialized JSON string.
    """

    return json.dumps(data, ensure_ascii=False, default=str)


def rewrite_search_query(question: str, max_terms: int = 10) -> str:
    """Convert a user question into a compact retrieval query.

    Args:
        question: Natural-language user question.
        max_terms: Maximum number of meaningful terms to keep.

    Returns:
        Keyword-oriented search query suitable for vector or graph retrieval.
    """

    tokens = [
        token
        for token in re.findall(r"[a-z0-9]+", question.lower())
        if len(token) > 2 and token not in QUERY_STOPWORDS
    ]
    deduped_tokens = list(dict.fromkeys(tokens))
    return " ".join(deduped_tokens[:max_terms]) or question


def rerank_documents(
    question: str,
    documents: list[dict[str, Any]],
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Rank retrieved documents by query overlap and backend score.

    Args:
        question: Original user question.
        documents: Candidate documents returned by retrieval tools.
        limit: Maximum number of documents to return.

    Returns:
        Documents sorted by rerank score, highest first.
    """

    query_tokens = set(rewrite_search_query(question).split())

    def score_document(document: dict[str, Any]) -> tuple[int, float]:
        """Score one document for reranking.

        Args:
            document: Retrieved document.

        Returns:
            Tuple of term-overlap score and original backend score.
        """

        text = _document_text(document)
        overlap = len(query_tokens.intersection(re.findall(r"[a-z0-9]+", text.lower())))
        backend_score = _backend_score(document)
        return overlap, backend_score

    ranked_documents = sorted(documents, key=score_document, reverse=True)
    return [
        {
            **document,
            "rerank_score": {
                "term_overlap": score_document(document)[0],
                "backend_score": score_document(document)[1],
            },
        }
        for document in ranked_documents[:limit]
    ]


@track_agent_tool("rewrite_search_query")
async def rewrite_search_query_tool(
    question: str,
    *,
    emit_event: Callable[[AgentEvent], None] | None = None,
) -> str:
    """Rewrite a natural-language question into a compact retrieval query.

    Args:
        question: Natural-language user question.
        emit_event: Optional callback for streaming structured tool events.

    Returns:
        Rewritten retrieval query.
    """

    emit_tool_event(
        emit_event,
        {
            "type": "tool_start",
            "tool": "rewrite_search_query",
            "input": {"question": question},
        },
    )
    rewritten_query = rewrite_search_query(question)
    record_agent_tool_results("rewrite_search_query", 1)
    emit_tool_event(
        emit_event,
        {
            "type": "tool_end",
            "tool": "rewrite_search_query",
            "output": {"count": 1},
        },
    )
    return rewritten_query


@track_agent_tool("search_openalex")
async def search_openalex(
    query: str,
    limit: int = 5,
    *,
    papers_service: PapersServiceClient,
    emit_event: Callable[[AgentEvent], None] | None = None,
) -> str:
    """Search OpenAlex for papers and return short metadata previews.

    Args:
        query: Keyword or phrase to search.
        limit: Maximum number of articles to return.
        papers_service: Service used for OpenAlex access.
        emit_event: Optional callback for streaming structured tool events.

    Returns:
        JSON list of compact article previews.
    """

    emit_tool_event(
        emit_event,
        {
            "type": "tool_start",
            "tool": "search_openalex",
            "input": {"query": query, "limit": limit},
        },
    )
    articles = await papers_service.get_articles(query=query, limit=limit)
    record_agent_tool_results("search_openalex", len(articles))
    emit_tool_event(
        emit_event,
        {
            "type": "tool_end",
            "tool": "search_openalex",
            "output": {"count": len(articles)},
        },
    )
    return to_json([article_preview(article) for article in articles])


@track_agent_tool("ingest_papers")
async def ingest_papers(
    query: str,
    limit: int = 5,
    *,
    papers_service: PapersServiceClient,
    emit_event: Callable[[AgentEvent], None] | None = None,
) -> str:
    """Search OpenAlex and store matching papers in vector and graph databases.

    Args:
        query: Keyword or phrase to search.
        limit: Maximum number of articles to ingest.
        papers_service: Service used for OpenAlex access and insertion.
        emit_event: Optional callback for streaming structured tool events.

    Returns:
        JSON object with insertion count and article previews.
    """

    emit_tool_event(
        emit_event,
        {
            "type": "tool_start",
            "tool": "ingest_papers",
            "input": {"query": query, "limit": limit},
        },
    )
    articles = await papers_service.get_articles(query=query, limit=limit)
    await papers_service.insert_articles(articles=articles)
    record_agent_tool_results("ingest_papers", len(articles))
    emit_tool_event(
        emit_event,
        {
            "type": "tool_end",
            "tool": "ingest_papers",
            "output": {"count": len(articles)},
        },
    )
    return to_json(
        {
            "inserted_count": len(articles),
            "papers": [article_preview(article) for article in articles],
        }
    )


@track_agent_tool("search_vector_database")
async def search_vector_database(
    query: str,
    limit: int = 5,
    *,
    vector_repository: PaperVectorRepository,
    emit_event: Callable[[AgentEvent], None] | None = None,
) -> str:
    """Search stored paper titles and abstracts in the vector database.

    Args:
        query: Retrieval query.
        limit: Maximum number of papers to return.
        vector_repository: Repository used for semantic search.
        emit_event: Optional callback for streaming structured tool events.

    Returns:
        JSON list of retrieved vector-search results.
    """

    emit_tool_event(
        emit_event,
        {
            "type": "tool_start",
            "tool": "search_vector_database",
            "input": {"query": query, "limit": limit},
        },
    )
    results = await vector_repository.search_papers(query=query, limit=limit)
    record_agent_tool_results("search_vector_database", len(results))
    emit_tool_event(
        emit_event,
        {
            "type": "tool_end",
            "tool": "search_vector_database",
            "output": {"count": len(results)},
        },
    )
    return to_json(results)


@track_agent_tool("search_graph_database")
async def search_graph_database(
    query: str,
    limit: int = 5,
    *,
    graph_repository: PaperGraphRepository,
    emit_event: Callable[[AgentEvent], None] | None = None,
) -> str:
    """Search stored paper metadata, topics, and sources in the graph database.

    Args:
        query: Retrieval query.
        limit: Maximum number of papers to return.
        graph_repository: Repository used for graph metadata search.
        emit_event: Optional callback for streaming structured tool events.

    Returns:
        JSON list of graph-search results.
    """

    emit_tool_event(
        emit_event,
        {
            "type": "tool_start",
            "tool": "search_graph_database",
            "input": {"query": query, "limit": limit},
        },
    )
    results = await graph_repository.search_papers(query=query, limit=limit)
    record_agent_tool_results("search_graph_database", len(results))
    emit_tool_event(
        emit_event,
        {
            "type": "tool_end",
            "tool": "search_graph_database",
            "output": {"count": len(results)},
        },
    )
    return to_json(results)


@track_agent_tool("get_graph_context")
async def get_graph_context(
    openalex_ids: list[str],
    *,
    graph_repository: PaperGraphRepository,
    emit_event: Callable[[AgentEvent], None] | None = None,
) -> str:
    """Get graph context for OpenAlex paper IDs from Neo4j.

    Args:
        openalex_ids: OpenAlex paper IDs to enrich.
        graph_repository: Repository used for graph context lookup.
        emit_event: Optional callback for streaming structured tool events.

    Returns:
        JSON list of graph context rows.
    """

    emit_tool_event(
        emit_event,
        {
            "type": "tool_start",
            "tool": "get_graph_context",
            "input": {"openalex_ids": openalex_ids},
        },
    )
    context = await graph_repository.get_paper_context(openalex_ids=openalex_ids)
    record_agent_tool_results("get_graph_context", len(context))
    emit_tool_event(
        emit_event,
        {
            "type": "tool_end",
            "tool": "get_graph_context",
            "output": {"count": len(context)},
        },
    )
    return to_json(context)


@track_agent_tool("rerank_documents")
async def rerank_documents_tool(
    question: str,
    documents_json: str,
    limit: int = 5,
    *,
    emit_event: Callable[[AgentEvent], None] | None = None,
) -> str:
    """Rerank retrieved documents for the original user question.

    Args:
        question: Original user question.
        documents_json: JSON list of retrieved documents.
        limit: Maximum number of documents to return.
        emit_event: Optional callback for streaming structured tool events.

    Returns:
        JSON list of reranked documents.
    """

    emit_tool_event(
        emit_event,
        {
            "type": "tool_start",
            "tool": "rerank_documents",
            "input": {"question": question, "limit": limit},
        },
    )
    try:
        documents = json.loads(documents_json)
    except json.JSONDecodeError:
        documents = []
    if not isinstance(documents, list):
        documents = []
    documents = [document for document in documents if isinstance(document, dict)]
    ranked_documents = rerank_documents(
        question=question,
        documents=documents,
        limit=limit,
    )
    record_agent_tool_results("rerank_documents", len(ranked_documents))
    emit_tool_event(
        emit_event,
        {
            "type": "tool_end",
            "tool": "rerank_documents",
            "output": {"count": len(ranked_documents)},
        },
    )
    return to_json(ranked_documents)


def log_agent_event(event: AgentEvent) -> None:
    """Write one structured agent event to application logs.

    Args:
        event: Structured agent event.
    """

    event_type = event["type"]
    log_data: dict[str, Any] = {"event_type": event_type}

    if "tool" in event:
        log_data["tool"] = event["tool"]
    match event_type:
        case "run_start":
            log_data["question"] = event["input"]["question"]
        case "run_end":
            log_data["answer_length"] = len(event["output"]["answer"])
        case "tool_start":
            log_data.update(event["input"])
        case "tool_end":
            log_data.update(event["output"])

    logger.info("agent_event", **log_data)


def emit_tool_event(
    emit_event: Callable[[AgentEvent], None] | None,
    event: AgentEvent,
) -> None:
    """Emit a tool event through logs and optional stream callback.

    Args:
        emit_event: Optional event callback.
        event: Structured tool event.
    """

    log_agent_event(event)
    if emit_event:
        emit_event(event)


def article_preview(article: OpenAlexArticle) -> dict[str, Any]:
    """Build a compact OpenAlex article preview.

    Args:
        article: OpenAlex article model.

    Returns:
        Metadata dictionary suitable for agent tool output.
    """

    return {
        "openalex_id": article.id,
        "doi": article.doi,
        "title": article.title,
        "publication_year": article.publication_year,
        "cited_by_count": article.cited_by_count,
    }


def _document_text(document: dict[str, Any]) -> str:
    """Build searchable text from a retrieved document.

    Args:
        document: Retrieved paper or graph result.

    Returns:
        Text assembled from title, abstract, topics, and source metadata.
    """

    payload = document.get("payload")
    paper = document.get("paper")
    text_parts = [
        document.get("title"),
        document.get("abstract"),
    ]

    if isinstance(payload, dict):
        text_parts.extend(
            [
                payload.get("title"),
                payload.get("abstract"),
                payload.get("abstract_text"),
            ]
        )

    if isinstance(paper, dict):
        text_parts.extend(
            [
                paper.get("title"),
                paper.get("abstract"),
            ]
        )

    topics = document.get("topics")
    sources = document.get("sources")
    if isinstance(topics, list):
        text_parts.extend(topics)
    if isinstance(sources, list):
        text_parts.extend(sources)

    return " ".join(str(part) for part in text_parts if part)


def _backend_score(document: dict[str, Any]) -> float:
    """Extract backend retrieval score from a document.

    Args:
        document: Retrieved paper or graph result.

    Returns:
        Numeric backend score, or `0.0` when no score is available.
    """

    score = document.get("score")
    if isinstance(score, int | float):
        return float(score)
    return 0.0
