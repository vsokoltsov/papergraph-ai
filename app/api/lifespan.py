import asyncio
import json
from collections.abc import AsyncIterator, Callable
from functools import lru_cache
from time import monotonic
from typing import Any
from uuid import uuid4

from opentelemetry import trace

from app.agents.research import AgentEvent, ResearchAgent, create_research_tools
from app.clients.openalex import OpenAlexClient
from app.db.neo4j import get_neo4j_driver
from app.db.postgres import get_postgres_engine
from app.db.qdrant import get_qdrant_client
from app.metrics import estimate_tokens
from app.repositories.feedback import AgentRunRecord, FeedbackRepository
from app.repositories.graph import GraphRepository
from app.repositories.vector import VectorRepository
from app.services.papers import PapersService
from app.settings import get_settings

tracer = trace.get_tracer(__name__)


@tracer.start_as_current_span("backend.run_research_agent")
async def run_research_agent(question: str) -> dict[str, Any]:
    run_id = str(uuid4())
    result = await execute_research_agent(question=question, run_id=run_id)
    return {
        "run_id": run_id,
        "answer": result["answer"],
        "events": result["events"],
    }


async def run_research_agent_stream(question: str) -> AsyncIterator[dict[str, Any]]:
    run_id = str(uuid4())
    event_queue: asyncio.Queue[AgentEvent | None] = asyncio.Queue()

    yield {"type": "run_id", "run_id": run_id}
    yield {"type": "status", "message": "Preparing research tools"}

    def emit_stream_event(event: AgentEvent) -> None:
        event_queue.put_nowait(event)

    yield {"type": "status", "message": "Running agent"}
    task = asyncio.create_task(
        execute_research_agent(
            question=question,
            run_id=run_id,
            emit_event=emit_stream_event,
        )
    )

    while not task.done() or not event_queue.empty():
        try:
            event = await asyncio.wait_for(event_queue.get(), timeout=0.5)
        except TimeoutError:
            if not task.done():
                yield {"type": "status", "message": "Still working"}
            continue

        if event is not None:
            yield {"type": "agent_event", "event": event}

    try:
        result = await task
    except Exception as error:
        yield {"type": "error", "message": str(error)}
        return

    yield {"type": "status", "message": "Streaming final answer"}
    for chunk in split_answer_chunks(str(result["answer"])):
        yield {"type": "answer_delta", "delta": chunk}

    yield {
        "type": "done",
        "run_id": run_id,
        "answer": result["answer"],
        "events": result["events"],
    }


async def execute_research_agent(
    question: str,
    run_id: str,
    emit_event: Callable[[AgentEvent], None] | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    events: list[AgentEvent] = []
    start = monotonic()

    def collect_event(event: AgentEvent) -> None:
        events.append(event)
        if emit_event:
            emit_event(event)

    openalex_client = OpenAlexClient(api_key=settings.OPENALEX_API_KEY)
    qdrant_db = get_qdrant_client(url=settings.QDRANT_URL)
    neo4j_db = get_neo4j_driver(
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD,
    )
    vector_repository = VectorRepository(
        db=qdrant_db,
        collection_name=settings.QDRANT_COLLECTION_NAME,
    )
    graph_repository = GraphRepository(db=neo4j_db)
    papers_service = PapersService(
        openalex_client=openalex_client,
        vector_repository=vector_repository,
        graph_repository=graph_repository,
    )
    tools = create_research_tools(
        papers_service=papers_service,
        vector_repository=vector_repository,
        graph_repository=graph_repository,
        emit_event=collect_event,
    )
    agent = ResearchAgent(
        tools=tools,
        model_name=settings.LLM_MODEL,
        api_key=settings.OPENAI_API_KEY,
        emit_event=collect_event,
    )

    answer = await agent.run(question)
    prompt_tokens = estimate_tokens(question, settings.LLM_MODEL)
    completion_tokens = estimate_tokens(answer, settings.LLM_MODEL)
    await get_feedback_repository().save_agent_run(
        AgentRunRecord(
            run_id=run_id,
            question=question,
            answer=str(answer),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            duration_seconds=monotonic() - start,
        )
    )
    return {"answer": answer, "events": events}


async def stream_sse(events: AsyncIterator[dict[str, Any]]) -> AsyncIterator[str]:
    async for event in events:
        yield f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"


def split_answer_chunks(answer: str, chunk_size: int = 24) -> list[str]:
    words = answer.split(" ")
    if not words:
        return [answer]

    chunks = []
    for index in range(0, len(words), chunk_size):
        chunks.append(" ".join(words[index : index + chunk_size]))
    return chunks


@lru_cache(maxsize=1)
def get_feedback_repository() -> FeedbackRepository:
    settings = get_settings()
    return FeedbackRepository(db=get_postgres_engine(settings.POSTGRES_DATABASE_URL))
