"""MCP server for exposing PaperGraph AI capabilities to external agents."""

from __future__ import annotations

from typing import Any

import logfire
from mcp.server.fastmcp import Context, FastMCP

from app.agents.research import ResearchAgent, create_research_tools
from app.clients.openalex import OpenAlexClient
from app.db.neo4j import get_neo4j_driver
from app.db.qdrant import get_qdrant_client
from app.logging import configure_logging
from app.repositories.graph import GraphRepository
from app.repositories.vector import VectorRepository
from app.services.papers import PapersService
from app.settings import Settings, get_settings
from app.tracing import configure_tracing

mcp = FastMCP(
    name="PaperGraph AI",
    instructions=(
        "Search, ingest, and analyze OpenAlex papers with Qdrant vector retrieval, Neo4j "
        "graph context, and the PaperGraph LangGraph research agent."
    ),
    stateless_http=True,
    json_response=True,
)


def safe_log_attributes(values: dict[str, Any]) -> dict[str, Any]:
    """Filter MCP call attributes before sending them to Logfire.

    Args:
        values: Keyword arguments passed to an MCP helper.

    Returns:
        Small attribute dictionary without settings objects or large payloads.
    """

    attributes = {}
    for key, value in values.items():
        match key:
            case "settings":
                continue
            case "question":
                attributes[key] = truncate(value)
            case "query":
                attributes[key] = truncate(value)
            case "openalex_ids":
                attributes["openalex_id_count"] = len(value)
            case "limit":
                attributes[key] = value
            case _:
                continue

    return attributes


def truncate(value: Any, max_length: int = 300) -> str:
    """Convert a value to a bounded string for observability attributes.

    Args:
        value: Value to convert.
        max_length: Maximum string length to keep.

    Returns:
        String value safe for structured logs.
    """

    text = str(value)
    if len(text) <= max_length:
        return text
    return f"{text[:max_length]}..."


def result_count(result: Any) -> int | None:
    """Infer a useful result count for a tool result.

    Args:
        result: MCP helper result.

    Returns:
        Number of returned records when that can be inferred.
    """

    match result:
        case list():
            return len(result)
        case {"inserted_count": int(count)}:
            return count
        case {"events": list(events)}:
            return len(events)
        case _:
            return None


@mcp.tool()
async def search_papers(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Search stored paper titles and abstracts in the vector database.

    Args:
        query: Semantic search query.
        limit: Maximum number of papers to return.

    Returns:
        Retrieved paper records with vector scores and payloads.
    """

    with logfire.span(
        "mcp tool search_papers",
        _span_name="mcp.search_papers",
        _tags=["mcp"],
        **safe_log_attributes({"query": query, "limit": limit}),
    ) as span:
        result = await search_papers_tool(query=query, limit=limit)
        span.set_attribute("result_count", result_count(result))
        return result


@mcp.tool()
async def search_paper_graph(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Search stored paper metadata, topics, and sources in Neo4j.

    Args:
        query: Keyword query for graph metadata.
        limit: Maximum number of papers to return.

    Returns:
        Graph search results with paper metadata, topics, sources, and graph scores.
    """

    with logfire.span(
        "mcp tool search_paper_graph",
        _span_name="mcp.search_paper_graph",
        _tags=["mcp"],
        **safe_log_attributes({"query": query, "limit": limit}),
    ) as span:
        result = await search_paper_graph_tool(query=query, limit=limit)
        span.set_attribute("result_count", result_count(result))
        return result


@mcp.tool()
async def get_paper_graph_context(openalex_ids: list[str]) -> list[dict[str, Any]]:
    """Get Neo4j graph context for OpenAlex paper IDs.

    Args:
        openalex_ids: OpenAlex paper IDs or URLs.

    Returns:
        Graph context including authors, institutions, sources, topics, and references.
    """

    with logfire.span(
        "mcp tool get_paper_graph_context",
        _span_name="mcp.get_paper_graph_context",
        _tags=["mcp"],
        **safe_log_attributes({"openalex_ids": openalex_ids}),
    ) as span:
        result = await get_paper_graph_context_tool(openalex_ids=openalex_ids)
        span.set_attribute("result_count", result_count(result))
        return result


@mcp.tool()
async def ingest_openalex_papers(
    query: str,
    limit: int = 5,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Search OpenAlex and ingest matching papers into Qdrant and Neo4j.

    Args:
        query: OpenAlex keyword query.
        limit: Maximum number of papers to ingest.
        ctx: MCP request context injected by the server.

    Returns:
        Summary of the ingestion result.
    """

    if ctx:
        await ctx.info(f"Ingesting OpenAlex papers for query={query!r}, limit={limit}")
    with logfire.span(
        "mcp tool ingest_openalex_papers",
        _span_name="mcp.ingest_openalex_papers",
        _tags=["mcp"],
        **safe_log_attributes({"query": query, "limit": limit}),
    ) as span:
        result = await ingest_openalex_papers_tool(query=query, limit=limit)
        span.set_attribute("result_count", result_count(result))
        return result


@mcp.tool()
async def ask_papergraph(question: str, ctx: Context | None = None) -> dict[str, Any]:
    """Run the full PaperGraph research agent for a question.

    Args:
        question: Research question to answer.
        ctx: MCP request context injected by the server.

    Returns:
        Final answer and structured agent events.
    """

    if ctx:
        await ctx.info(f"Running PaperGraph agent for question={question!r}")
    with logfire.span(
        "mcp tool ask_papergraph",
        _span_name="mcp.ask_papergraph",
        _tags=["mcp"],
        **safe_log_attributes({"question": question}),
    ) as span:
        result = await ask_papergraph_tool(question=question)
        span.set_attribute("result_count", result_count(result))
        return result


async def search_papers_tool(
    query: str,
    limit: int = 5,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    """Search papers through the vector repository.

    Args:
        query: Semantic search query.
        limit: Maximum number of papers to return.
        settings: Optional settings override for tests.

    Returns:
        Retrieved paper records.
    """

    vector_repository = build_vector_repository(settings=settings)
    return await vector_repository.search_papers(query=query, limit=limit)


async def search_paper_graph_tool(
    query: str,
    limit: int = 5,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    """Search papers through the graph repository.

    Args:
        query: Keyword query for graph metadata.
        limit: Maximum number of papers to return.
        settings: Optional settings override for tests.

    Returns:
        Graph search results.
    """

    graph_repository = build_graph_repository(settings=settings)
    return await graph_repository.search_papers(query=query, limit=limit)


async def get_paper_graph_context_tool(
    openalex_ids: list[str],
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    """Get graph context for papers.

    Args:
        openalex_ids: OpenAlex paper IDs or URLs.
        settings: Optional settings override for tests.

    Returns:
        Graph context rows.
    """

    graph_repository = build_graph_repository(settings=settings)
    return await graph_repository.get_paper_context(openalex_ids=openalex_ids)


async def ingest_openalex_papers_tool(
    query: str,
    limit: int = 5,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Ingest OpenAlex papers into vector and graph stores.

    Args:
        query: OpenAlex keyword query.
        limit: Maximum number of papers to ingest.
        settings: Optional settings override for tests.

    Returns:
        Ingestion summary with inserted paper previews.
    """

    service = build_papers_service(settings=settings)
    articles = await service.get_articles(query=query, limit=limit)
    await service.insert_articles(articles=articles)
    return {
        "query": query,
        "inserted_count": len(articles),
        "papers": [
            {
                "openalex_id": article.id,
                "doi": article.doi,
                "title": article.title,
                "publication_year": article.publication_year,
                "cited_by_count": article.cited_by_count,
            }
            for article in articles
        ],
    }


async def ask_papergraph_tool(
    question: str,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Run the full PaperGraph research agent.

    Args:
        question: Research question to answer.
        settings: Optional settings override for tests.

    Returns:
        Final answer and structured agent events.
    """

    settings = settings or get_settings()
    events = []
    service = build_papers_service(settings=settings)
    vector_repository = build_vector_repository(settings=settings)
    graph_repository = build_graph_repository(settings=settings)
    tools = create_research_tools(
        papers_service=service,
        vector_repository=vector_repository,
        graph_repository=graph_repository,
        emit_event=events.append,
    )
    agent = ResearchAgent(
        tools=tools,
        model_name=settings.LLM_MODEL,
        api_key=settings.OPENAI_API_KEY,
        emit_event=events.append,
    )
    answer = await agent.run(question)
    return {"answer": answer, "events": events}


def build_papers_service(settings: Settings | None = None) -> PapersService:
    """Build the paper service used by MCP tools.

    Args:
        settings: Optional settings override for tests.

    Returns:
        Paper service configured with OpenAlex, Qdrant, and Neo4j clients.
    """

    settings = settings or get_settings()
    return PapersService(
        openalex_client=OpenAlexClient(api_key=settings.OPENALEX_API_KEY),
        vector_repository=build_vector_repository(settings=settings),
        graph_repository=build_graph_repository(settings=settings),
    )


def build_vector_repository(settings: Settings | None = None) -> VectorRepository:
    """Build the vector repository used by MCP tools.

    Args:
        settings: Optional settings override for tests.

    Returns:
        Vector repository connected to Qdrant.
    """

    settings = settings or get_settings()
    return VectorRepository(
        db=get_qdrant_client(url=settings.QDRANT_URL),
        collection_name=settings.QDRANT_COLLECTION_NAME,
    )


def build_graph_repository(settings: Settings | None = None) -> GraphRepository:
    """Build the graph repository used by MCP tools.

    Args:
        settings: Optional settings override for tests.

    Returns:
        Graph repository connected to Neo4j.
    """

    settings = settings or get_settings()
    return GraphRepository(
        db=get_neo4j_driver(
            uri=settings.NEO4J_URI,
            user=settings.NEO4J_USER,
            password=settings.NEO4J_PASSWORD,
        )
    )


def configure_mcp_runtime(settings: Settings | None = None) -> Settings:
    """Configure logging and tracing for the MCP process.

    Args:
        settings: Optional settings override for tests.

    Returns:
        Settings used for runtime configuration.
    """

    settings = settings or get_settings()
    configure_logging(settings.LOG_LEVEL)
    configure_tracing(settings)
    return settings


def main() -> None:
    """Run the MCP server with the default stdio transport."""

    configure_mcp_runtime()
    mcp.run()


if __name__ == "__main__":
    main()
