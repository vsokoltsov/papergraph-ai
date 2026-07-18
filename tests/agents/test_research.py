import json
from dataclasses import dataclass, field
from typing import Any

import pytest

from app.agents.research import create_research_tools
from app.clients.openalex import OpenAlexArticle


@dataclass
class FakePapersService:
    articles: list[OpenAlexArticle]
    inserted_articles: list[OpenAlexArticle] = field(default_factory=list)

    async def get_articles(self, query: str, limit: int = 20) -> list[OpenAlexArticle]:
        assert query == "graph rag"
        assert limit == 1
        return self.articles

    async def insert_articles(self, articles: list[OpenAlexArticle]) -> None:
        self.inserted_articles.extend(articles)


@dataclass
class FakeVectorRepository:
    async def search_papers(self, query: str | list[float], limit: int = 5) -> list[dict[str, Any]]:
        assert query == "graph rag"
        assert limit == 1
        return [
            {
                "id": "00000000-0000-0000-0000-000000000001",
                "score": 0.9,
                "payload": {"openalex_id": "https://openalex.org/W1"},
            }
        ]


@dataclass
class FakeGraphRepository:
    async def get_paper_context(self, openalex_ids: list[str]) -> list[dict]:
        assert openalex_ids == ["https://openalex.org/W1"]
        return [{"paper": {"openalex_id": "https://openalex.org/W1", "title": "Graph RAG"}}]


def _tools_by_name():
    article = OpenAlexArticle(
        id="https://openalex.org/W1",
        doi="https://doi.org/10.123/test",
        title="Graph RAG",
        publication_year=2024,
        cited_by_count=7,
    )
    papers_service = FakePapersService(articles=[article])
    tools = create_research_tools(
        papers_service=papers_service,
        vector_repository=FakeVectorRepository(),
        graph_repository=FakeGraphRepository(),
    )

    return {tool.name: tool for tool in tools}, papers_service


def _tools_by_name_with_logs():
    article = OpenAlexArticle(id="https://openalex.org/W1", title="Graph RAG")
    papers_service = FakePapersService(articles=[article])
    logs = []
    tools = create_research_tools(
        papers_service=papers_service,
        vector_repository=FakeVectorRepository(),
        graph_repository=FakeGraphRepository(),
        log=logs.append,
    )

    return {tool.name: tool for tool in tools}, logs


@pytest.mark.asyncio
async def test_search_openalex_tool_returns_article_previews() -> None:
    tools, _ = _tools_by_name()

    result = await tools["search_openalex"].ainvoke({"query": "graph rag", "limit": 1})

    assert json.loads(result) == [
        {
            "openalex_id": "https://openalex.org/W1",
            "doi": "https://doi.org/10.123/test",
            "title": "Graph RAG",
            "publication_year": 2024,
            "cited_by_count": 7,
        }
    ]


@pytest.mark.asyncio
async def test_ingest_papers_tool_stores_articles() -> None:
    tools, papers_service = _tools_by_name()

    result = await tools["ingest_papers"].ainvoke({"query": "graph rag", "limit": 1})

    assert json.loads(result)["inserted_count"] == 1
    assert papers_service.inserted_articles == papers_service.articles


@pytest.mark.asyncio
async def test_search_vector_database_tool_returns_matches() -> None:
    tools, _ = _tools_by_name()

    result = await tools["search_vector_database"].ainvoke({"query": "graph rag", "limit": 1})

    assert json.loads(result) == [
        {
            "id": "00000000-0000-0000-0000-000000000001",
            "score": 0.9,
            "payload": {"openalex_id": "https://openalex.org/W1"},
        }
    ]


@pytest.mark.asyncio
async def test_get_graph_context_tool_returns_context() -> None:
    tools, _ = _tools_by_name()

    result = await tools["get_graph_context"].ainvoke({"openalex_ids": ["https://openalex.org/W1"]})

    assert json.loads(result) == [
        {"paper": {"openalex_id": "https://openalex.org/W1", "title": "Graph RAG"}}
    ]


@pytest.mark.asyncio
async def test_tools_emit_action_logs_when_logger_is_provided() -> None:
    tools, logs = _tools_by_name_with_logs()

    await tools["search_openalex"].ainvoke({"query": "graph rag", "limit": 1})

    assert logs == [
        "[agent] search_openalex query='graph rag' limit=1",
        "[agent] search_openalex found=1",
    ]
