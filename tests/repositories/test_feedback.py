from typing import Any, cast

import pytest

from app.repositories.feedback import AgentRunRecord, FeedbackRecord, FeedbackRepository


@pytest.mark.asyncio
async def test_save_agent_run_upserts_run() -> None:
    engine = FakeEngine()
    repository = FeedbackRepository(db=cast(Any, engine))

    await repository.save_agent_run(
        AgentRunRecord(
            run_id="run-1",
            question="What is GraphRAG?",
            answer="GraphRAG answer",
            approach="vector_plus_graph",
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
            duration_seconds=1.5,
        )
    )

    query, params = engine.connection.calls[-1]
    assert "INSERT INTO agent_runs" in query
    assert "ON CONFLICT (run_id)" in query
    assert params == {}


@pytest.mark.asyncio
async def test_save_feedback_inserts_feedback() -> None:
    engine = FakeEngine()
    repository = FeedbackRepository(db=cast(Any, engine))

    await repository.save_feedback(
        FeedbackRecord(
            run_id="run-1",
            rating="thumbs_up",
            comment="Useful answer.",
        )
    )

    query, params = engine.connection.calls[-1]
    assert "INSERT INTO feedback" in query
    assert params == {}


@pytest.mark.asyncio
async def test_schema_is_created_once() -> None:
    engine = FakeEngine()
    repository = FeedbackRepository(db=cast(Any, engine))

    await repository.ensure_schema()
    call_count = len(engine.connection.calls)
    await repository.ensure_schema()

    assert call_count > 0
    assert len(engine.connection.calls) == call_count
    assert engine.connection.schema_created


class FakeConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.schema_created = False

    async def execute(self, query: Any, params: dict[str, Any] | None = None) -> None:
        self.calls.append((str(query), params or {}))

    async def run_sync(self, callback: Any) -> None:
        self.schema_created = True
        self.calls.append((f"run_sync:{callback.__name__}", {}))


class FakeTransaction:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    async def __aenter__(self) -> FakeConnection:
        return self.connection

    async def __aexit__(self, *args: object) -> None:
        return None


class FakeEngine:
    def __init__(self) -> None:
        self.connection = FakeConnection()

    def begin(self) -> FakeTransaction:
        return FakeTransaction(self.connection)
