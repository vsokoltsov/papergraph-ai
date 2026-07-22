import json
from dataclasses import dataclass, field
from typing import Any

import pytest

from app.agents.research import (
    ResearchAgent,
    create_research_tools,
    format_agent_event,
    rerank_documents,
    rewrite_search_query,
)
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
        assert limit in {1, 5}
        return [
            {
                "id": "00000000-0000-0000-0000-000000000001",
                "score": 0.9,
                "payload": {"openalex_id": "https://openalex.org/W1"},
            }
        ]


@dataclass
class FakeGraphRepository:
    async def search_papers(self, query: str, limit: int = 5) -> list[dict]:
        assert query == "graph rag"
        assert limit in {1, 5}
        return [{"paper": {"openalex_id": "https://openalex.org/W1", "title": "Graph RAG"}}]

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


def _tools_by_name_with_events():
    article = OpenAlexArticle(id="https://openalex.org/W1", title="Graph RAG")
    papers_service = FakePapersService(articles=[article])
    events = []
    tools = create_research_tools(
        papers_service=papers_service,
        vector_repository=FakeVectorRepository(),
        graph_repository=FakeGraphRepository(),
        emit_event=events.append,
    )

    return {tool.name: tool for tool in tools}, events


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


def test_rewrite_search_query_keeps_retrieval_terms() -> None:
    assert (
        rewrite_search_query(
            "Which papers compare neighborhood-level retrieval with community-level retrieval?"
        )
        == "neighborhood level retrieval community"
    )


@pytest.mark.asyncio
async def test_rewrite_search_query_tool_returns_rewritten_query() -> None:
    tools, _ = _tools_by_name()

    result = await tools["rewrite_search_query"].ainvoke(
        {
            "question": (
                "Which papers compare neighborhood-level retrieval with community-level retrieval?"
            )
        }
    )

    assert result == "neighborhood level retrieval community"


def test_rerank_documents_prioritizes_question_overlap() -> None:
    documents = [
        {
            "score": 0.99,
            "payload": {"title": "General retrieval augmented generation survey"},
        },
        {
            "score": 0.40,
            "payload": {
                "title": "Neighborhood retrieval and community retrieval over medical graph"
            },
        },
    ]

    ranked_documents = rerank_documents(
        question="community neighborhood retrieval over a medical knowledge graph",
        documents=documents,
        limit=2,
    )

    assert ranked_documents[0]["payload"]["title"] == (
        "Neighborhood retrieval and community retrieval over medical graph"
    )
    assert ranked_documents[0]["rerank_score"] == {
        "term_overlap": 6,
        "backend_score": 0.4,
    }


@pytest.mark.asyncio
async def test_rerank_documents_tool_returns_ranked_documents() -> None:
    tools, _ = _tools_by_name()

    result = await tools["rerank_documents"].ainvoke(
        {
            "question": "graph rag",
            "documents_json": json.dumps(
                [
                    {"score": 0.9, "payload": {"title": "Other paper"}},
                    {"score": 0.1, "payload": {"title": "Graph RAG"}},
                ]
            ),
            "limit": 1,
        }
    )

    assert json.loads(result) == [
        {
            "score": 0.1,
            "payload": {"title": "Graph RAG"},
            "rerank_score": {"term_overlap": 2, "backend_score": 0.1},
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
async def test_search_graph_database_tool_returns_matches() -> None:
    tools, _ = _tools_by_name()

    result = await tools["search_graph_database"].ainvoke({"query": "graph rag", "limit": 1})

    assert json.loads(result) == [
        {"paper": {"openalex_id": "https://openalex.org/W1", "title": "Graph RAG"}}
    ]


@pytest.mark.asyncio
async def test_create_research_tools_filters_enabled_tools() -> None:
    tools, _ = _tools_by_name()
    filtered_tools = create_research_tools(
        papers_service=FakePapersService(articles=[]),
        vector_repository=FakeVectorRepository(),
        graph_repository=FakeGraphRepository(),
        enabled_tools={"search_vector_database"},
    )

    assert "search_graph_database" in tools
    assert [tool.name for tool in filtered_tools] == ["search_vector_database"]


@pytest.mark.asyncio
async def test_tools_emit_structured_action_events() -> None:
    tools, events = _tools_by_name_with_events()

    await tools["search_openalex"].ainvoke({"query": "graph rag", "limit": 1})

    assert events == [
        {
            "type": "tool_start",
            "tool": "search_openalex",
            "input": {"query": "graph rag", "limit": 1},
        },
        {
            "type": "tool_end",
            "tool": "search_openalex",
            "output": {"count": 1},
        },
    ]


def test_format_agent_event_returns_cli_log_line() -> None:
    assert (
        format_agent_event(
            {
                "type": "tool_start",
                "tool": "search_vector_database",
                "input": {"query": "graph rag", "limit": 5},
            }
        )
        == "[agent] search_vector_database query='graph rag' limit=5"
    )


@pytest.mark.asyncio
async def test_research_agent_runs_langgraph_workflow(monkeypatch) -> None:
    events = []
    article = OpenAlexArticle(id="https://openalex.org/W1", title="Graph RAG")
    papers_service = FakePapersService(articles=[article])
    tools = create_research_tools(
        papers_service=papers_service,
        vector_repository=FakeVectorRepository(),
        graph_repository=FakeGraphRepository(),
        emit_event=events.append,
    )

    class FakeChatOpenAI:
        """Fake chat model used to avoid external LLM calls."""

        def __init__(self, **kwargs: Any) -> None:
            """Store initialization arguments for assertions.

            Args:
                **kwargs: Chat model configuration.
            """

            self.kwargs = kwargs

        async def ainvoke(self, messages: list[Any]) -> Any:
            """Return a deterministic answer for workflow tests.

            Args:
                messages: Messages passed to the model.

            Returns:
                Fake message object with answer content.
            """

            assert "Reranked retrieved papers JSON" in messages[-1].content
            assert "Graph context JSON" in messages[-1].content
            return FakeMessage(content="Graph RAG answer.")

    @dataclass
    class FakeMessage:
        """Minimal message object returned by the fake chat model."""

        content: str

    monkeypatch.setattr("app.agents.research.ChatOpenAI", FakeChatOpenAI)

    agent = ResearchAgent(
        tools=tools,
        model_name="test-model",
        api_key="test-key",
        emit_event=events.append,
    )

    answer = await agent.run("graph rag")

    assert answer == "Graph RAG answer."
    assert [event["type"] for event in agent.events] == ["run_start", "run_end"]
    assert [event["tool"] for event in events if "tool" in event] == [
        "rewrite_search_query",
        "rewrite_search_query",
        "search_vector_database",
        "search_vector_database",
        "rerank_documents",
        "rerank_documents",
        "get_graph_context",
        "get_graph_context",
    ]
