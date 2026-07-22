from dataclasses import dataclass, field
from typing import Any

import pytest

import app.mcp as papergraph_mcp
from app.clients.openalex import OpenAlexArticle
from app.settings import Settings


@dataclass
class FakeVectorRepository:
    results: list[dict[str, Any]]

    async def search_papers(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        assert query == "graph rag"
        assert limit == 3
        return self.results


@dataclass
class FakeGraphRepository:
    search_results: list[dict[str, Any]]
    context_results: list[dict[str, Any]]

    async def search_papers(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        assert query == "graph rag"
        assert limit == 3
        return self.search_results

    async def get_paper_context(self, openalex_ids: list[str]) -> list[dict[str, Any]]:
        assert openalex_ids == ["https://openalex.org/W1"]
        return self.context_results


@dataclass
class FakePapersService:
    articles: list[OpenAlexArticle]
    inserted_articles: list[OpenAlexArticle] = field(default_factory=list)

    async def get_articles(self, query: str, limit: int = 5) -> list[OpenAlexArticle]:
        assert query == "graph rag"
        assert limit == 3
        return self.articles

    async def insert_articles(self, articles: list[OpenAlexArticle]) -> None:
        self.inserted_articles.extend(articles)


class FakeResearchAgent:
    def __init__(self, tools, model_name: str, api_key: str, emit_event) -> None:
        assert tools == ["tool"]
        assert model_name == "test-model"
        assert api_key == "test-key"
        self.emit_event = emit_event

    async def run(self, question: str) -> str:
        assert question == "What is graph rag?"
        self.emit_event({"event_type": "run_start", "question": question})
        return "Graph RAG answer"


def test_safe_log_attributes_filters_sensitive_and_large_values() -> None:
    attributes = papergraph_mcp.safe_log_attributes(
        {
            "query": "graph rag",
            "question": "x" * 400,
            "openalex_ids": ["https://openalex.org/W1", "https://openalex.org/W2"],
            "limit": 3,
            "settings": Settings(OPENAI_API_KEY="secret"),
            "payload": {"large": "ignored"},
        }
    )

    assert attributes == {
        "query": "graph rag",
        "question": f"{'x' * 300}...",
        "openalex_id_count": 2,
        "limit": 3,
    }


def test_result_count_handles_mcp_result_shapes() -> None:
    assert papergraph_mcp.result_count([{"id": "paper-1"}]) == 1
    assert papergraph_mcp.result_count({"inserted_count": 2}) == 2
    assert papergraph_mcp.result_count({"events": [{}, {}]}) == 2
    assert papergraph_mcp.result_count({"answer": "done"}) is None


@pytest.mark.asyncio
async def test_search_papers_tool_uses_vector_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = [{"id": "paper-1", "score": 0.9}]

    monkeypatch.setattr(
        papergraph_mcp,
        "build_vector_repository",
        lambda settings=None: FakeVectorRepository(results=expected),
    )

    result = await papergraph_mcp.search_papers_tool(query="graph rag", limit=3)

    assert result == expected


@pytest.mark.asyncio
async def test_search_paper_graph_tool_uses_graph_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = [{"paper": {"openalex_id": "https://openalex.org/W1"}}]

    monkeypatch.setattr(
        papergraph_mcp,
        "build_graph_repository",
        lambda settings=None: FakeGraphRepository(search_results=expected, context_results=[]),
    )

    result = await papergraph_mcp.search_paper_graph_tool(query="graph rag", limit=3)

    assert result == expected


@pytest.mark.asyncio
async def test_get_paper_graph_context_tool_uses_graph_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = [{"paper": {"openalex_id": "https://openalex.org/W1"}, "authors": []}]

    monkeypatch.setattr(
        papergraph_mcp,
        "build_graph_repository",
        lambda settings=None: FakeGraphRepository(search_results=[], context_results=expected),
    )

    result = await papergraph_mcp.get_paper_graph_context_tool(
        openalex_ids=["https://openalex.org/W1"]
    )

    assert result == expected


@pytest.mark.asyncio
async def test_ingest_openalex_papers_tool_stores_articles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    article = OpenAlexArticle(
        id="https://openalex.org/W1",
        doi="https://doi.org/10.123/test",
        title="Graph RAG",
        publication_year=2024,
        cited_by_count=7,
    )
    service = FakePapersService(articles=[article])

    monkeypatch.setattr(papergraph_mcp, "build_papers_service", lambda settings=None: service)

    result = await papergraph_mcp.ingest_openalex_papers_tool(query="graph rag", limit=3)

    assert result == {
        "query": "graph rag",
        "inserted_count": 1,
        "papers": [
            {
                "openalex_id": "https://openalex.org/W1",
                "doi": "https://doi.org/10.123/test",
                "title": "Graph RAG",
                "publication_year": 2024,
                "cited_by_count": 7,
            }
        ],
    }
    assert service.inserted_articles == [article]


@pytest.mark.asyncio
async def test_ask_papergraph_tool_returns_answer_and_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(papergraph_mcp, "build_papers_service", lambda settings=None: object())
    monkeypatch.setattr(papergraph_mcp, "build_vector_repository", lambda settings=None: object())
    monkeypatch.setattr(papergraph_mcp, "build_graph_repository", lambda settings=None: object())
    monkeypatch.setattr(papergraph_mcp, "create_research_tools", lambda **kwargs: ["tool"])
    monkeypatch.setattr(papergraph_mcp, "ResearchAgent", FakeResearchAgent)

    result = await papergraph_mcp.ask_papergraph_tool(
        question="What is graph rag?",
        settings=Settings(LLM_MODEL="test-model", OPENAI_API_KEY="test-key"),
    )

    assert result == {
        "answer": "Graph RAG answer",
        "events": [{"event_type": "run_start", "question": "What is graph rag?"}],
    }
