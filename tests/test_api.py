from typing import Any

import pytest
from fastapi.testclient import TestClient

import app.api as api
from app.api import create_app
from app.repositories.feedback import AgentRunRecord, FeedbackRecord
from app.settings import Settings


def test_health_returns_ok() -> None:
    app = create_app(agent_runner=_fake_agent_runner)
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_agent_runs_endpoint_returns_answer_and_events() -> None:
    app = create_app(agent_runner=_fake_agent_runner)
    client = TestClient(app)

    response = client.post(
        "/agent/runs",
        json={"question": "Find graph rag papers"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "run_id": "run-1",
        "answer": "Graph RAG answer",
        "events": [
            {
                "type": "run_start",
                "input": {"question": "Find graph rag papers"},
            },
            {
                "type": "run_end",
                "output": {"answer": "Graph RAG answer"},
            },
        ],
    }


def test_agent_runs_stream_endpoint_returns_sse_events() -> None:
    app = create_app(
        agent_runner=_fake_agent_runner,
        agent_stream_runner=_fake_agent_stream_runner,
    )
    client = TestClient(app)

    response = client.post(
        "/agent/runs/stream",
        json={"question": "Find graph rag papers"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert 'data: {"type": "run_id", "run_id": "run-1"}' in response.text
    assert 'data: {"type": "answer_delta", "delta": "Graph RAG answer"}' in response.text
    assert 'data: {"type": "done", "run_id": "run-1"' in response.text


def test_metrics_endpoint_exposes_prometheus_metrics() -> None:
    app = create_app(agent_runner=_fake_agent_runner)
    client = TestClient(app)

    client.get("/health")
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "papergraph_http_requests_total" in response.text


def test_feedback_endpoint_stores_feedback() -> None:
    feedback_repository = FakeFeedbackRepository()
    app = create_app(
        agent_runner=_fake_agent_runner,
        feedback_repository=feedback_repository,
    )
    client = TestClient(app)

    response = client.post(
        "/feedback",
        json={
            "run_id": "run-1",
            "rating": "thumbs_down",
            "comment": "Missing graph context.",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert feedback_repository.records == [
        FeedbackRecord(
            run_id="run-1",
            rating="thumbs_down",
            comment="Missing graph context.",
        )
    ]


def test_feedback_endpoint_rejects_unknown_rating() -> None:
    app = create_app(
        agent_runner=_fake_agent_runner,
        feedback_repository=FakeFeedbackRepository(),
    )
    client = TestClient(app)

    response = client.post(
        "/feedback",
        json={
            "run_id": "run-1",
            "rating": "bad",
        },
    )

    assert response.status_code == 422


def test_get_feedback_repository_uses_postgres_settings(monkeypatch) -> None:
    api.get_feedback_repository.cache_clear()
    created_urls: list[str] = []

    monkeypatch.setattr(
        api,
        "get_settings",
        lambda: Settings(POSTGRES_DATABASE_URL="postgresql+asyncpg://example"),
    )

    def fake_get_postgres_engine(url: str) -> str:
        created_urls.append(url)
        return "engine"

    monkeypatch.setattr(api, "get_postgres_engine", fake_get_postgres_engine)

    repository = api.get_feedback_repository()

    assert repository.db == "engine"
    assert created_urls == ["postgresql+asyncpg://example"]
    api.get_feedback_repository.cache_clear()


@pytest.mark.asyncio
async def test_run_research_agent_saves_run(monkeypatch) -> None:
    feedback_repository = FakeFeedbackRepository()
    captured_tools: dict[str, Any] = {}

    monkeypatch.setattr(
        api,
        "get_settings",
        lambda: Settings(
            OPENALEX_API_KEY="openalex-key",
            OPENAI_API_KEY="openai-key",
            LLM_MODEL="test-model",
            QDRANT_URL="http://qdrant",
            QDRANT_COLLECTION_NAME="papers",
            NEO4J_URI="bolt://neo4j:7687",
            NEO4J_USER="neo4j",
            NEO4J_PASSWORD="password",
        ),
    )
    monkeypatch.setattr(api, "uuid4", lambda: "run-1")
    monkeypatch.setattr(api, "monotonic", FakeClock([10.0, 11.5]))
    monkeypatch.setattr(api, "OpenAlexClient", lambda api_key: FakeOpenAlexClient(api_key))
    monkeypatch.setattr(api, "get_qdrant_client", lambda url: f"qdrant:{url}")
    monkeypatch.setattr(api, "get_neo4j_driver", lambda uri, user, password: f"neo4j:{uri}")
    monkeypatch.setattr(api, "get_feedback_repository", lambda: feedback_repository)
    monkeypatch.setattr(api, "ResearchAgent", FakeResearchAgent)
    monkeypatch.setattr(api, "estimate_tokens", lambda value, model_name: len(str(value)))

    def fake_create_research_tools(**kwargs: Any) -> list[str]:
        captured_tools.update(kwargs)
        return ["tool"]

    monkeypatch.setattr(api, "create_research_tools", fake_create_research_tools)

    result = await api.run_research_agent("What is GraphRAG?")

    assert result == {
        "run_id": "run-1",
        "answer": "Agent answer.",
        "events": [
            {"type": "run_start", "input": {"question": "What is GraphRAG?"}},
            {"type": "run_end", "output": {"answer": "Agent answer."}},
        ],
    }
    assert captured_tools["emit_event"] is not None
    assert feedback_repository.agent_runs == [
        AgentRunRecord(
            run_id="run-1",
            question="What is GraphRAG?",
            answer="Agent answer.",
            prompt_tokens=len("What is GraphRAG?"),
            completion_tokens=len("Agent answer."),
            total_tokens=len("What is GraphRAG?") + len("Agent answer."),
            duration_seconds=1.5,
        )
    ]


@pytest.mark.asyncio
async def test_run_research_agent_stream_yields_progress_and_answer(monkeypatch) -> None:
    async def fake_execute_research_agent(
        question: str,
        run_id: str,
        emit_event: Any = None,
    ) -> dict[str, Any]:
        emit_event({"type": "run_start", "input": {"question": question}})
        return {
            "answer": "Graph RAG answer",
            "events": [{"type": "run_start", "input": {"question": question}}],
        }

    monkeypatch.setattr(api, "uuid4", lambda: "run-1")
    monkeypatch.setattr(api, "execute_research_agent", fake_execute_research_agent)
    monkeypatch.setattr(api, "split_answer_chunks", lambda answer: ["Graph RAG", "answer"])

    events = [event async for event in api.run_research_agent_stream("What is GraphRAG?")]

    assert events == [
        {"type": "run_id", "run_id": "run-1"},
        {
            "type": "agent_event",
            "event": {"type": "run_start", "input": {"question": "What is GraphRAG?"}},
        },
        {"type": "answer_delta", "delta": "Graph RAG"},
        {"type": "answer_delta", "delta": "answer"},
        {
            "type": "done",
            "run_id": "run-1",
            "answer": "Graph RAG answer",
            "events": [{"type": "run_start", "input": {"question": "What is GraphRAG?"}}],
        },
    ]


@pytest.mark.asyncio
async def test_run_research_agent_stream_yields_error(monkeypatch) -> None:
    async def fake_execute_research_agent(
        question: str,
        run_id: str,
        emit_event: Any = None,
    ) -> dict[str, Any]:
        raise RuntimeError("backend failed")

    monkeypatch.setattr(api, "uuid4", lambda: "run-1")
    monkeypatch.setattr(api, "execute_research_agent", fake_execute_research_agent)

    events = [event async for event in api.run_research_agent_stream("What is GraphRAG?")]

    assert events == [
        {"type": "run_id", "run_id": "run-1"},
        {"type": "error", "message": "backend failed"},
    ]


def test_split_answer_chunks_groups_words() -> None:
    assert api.split_answer_chunks("one two three four five", chunk_size=2) == [
        "one two",
        "three four",
        "five",
    ]


@pytest.mark.asyncio
async def test_stream_sse_serializes_events() -> None:
    async def events() -> Any:
        yield {"type": "run_id", "run_id": "run-1"}

    serialized = [event async for event in api.stream_sse(events())]

    assert serialized == ['data: {"type": "run_id", "run_id": "run-1"}\n\n']


async def _fake_agent_runner(question: str) -> dict[str, Any]:
    return {
        "run_id": "run-1",
        "answer": "Graph RAG answer",
        "events": [
            {"type": "run_start", "input": {"question": question}},
            {"type": "run_end", "output": {"answer": "Graph RAG answer"}},
        ],
    }


async def _fake_agent_stream_runner(question: str) -> Any:
    yield {"type": "run_id", "run_id": "run-1"}
    yield {
        "type": "agent_event",
        "event": {"type": "run_start", "input": {"question": question}},
    }
    yield {"type": "answer_delta", "delta": "Graph RAG answer"}
    yield {
        "type": "done",
        "run_id": "run-1",
        "answer": "Graph RAG answer",
        "events": [{"type": "run_start", "input": {"question": question}}],
    }


class FakeFeedbackRepository:
    def __init__(self) -> None:
        self.records: list[FeedbackRecord] = []
        self.agent_runs: list[AgentRunRecord] = []

    async def save_feedback(self, record: FeedbackRecord) -> None:
        self.records.append(record)

    async def save_agent_run(self, record: AgentRunRecord) -> None:
        self.agent_runs.append(record)


class FakeClock:
    def __init__(self, values: list[float]) -> None:
        self.values = values

    def __call__(self) -> float:
        return self.values.pop(0)


class FakeOpenAlexClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key


class FakeResearchAgent:
    def __init__(
        self,
        tools: list[str],
        model_name: str,
        api_key: str,
        emit_event: Any,
    ) -> None:
        self.emit_event = emit_event

    async def run(self, question: str) -> str:
        self.emit_event({"type": "run_start", "input": {"question": question}})
        self.emit_event({"type": "run_end", "output": {"answer": "Agent answer."}})
        return "Agent answer."
