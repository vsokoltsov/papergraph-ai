from collections.abc import Awaitable, Callable
from functools import lru_cache
from time import monotonic
from typing import Any, Protocol
from uuid import uuid4

from fastapi import FastAPI
from opentelemetry import trace
from pydantic import BaseModel, Field

from app.agents.research import AgentEvent, ResearchAgent, create_research_tools
from app.clients.openalex import OpenAlexClient
from app.db.neo4j import get_neo4j_driver
from app.db.postgres import get_postgres_engine
from app.db.qdrant import get_qdrant_client
from app.logging import configure_logging
from app.metrics import estimate_tokens, instrument_prometheus
from app.repositories.feedback import AgentRunRecord, FeedbackRecord, FeedbackRepository
from app.repositories.graph import GraphRepository
from app.repositories.vector import VectorRepository
from app.services.papers import PapersService
from app.settings import Settings, get_settings
from app.tracing import configure_tracing, instrument_fastapi_app

tracer = trace.get_tracer(__name__)
AgentRunner = Callable[[str], Awaitable[dict[str, Any]]]


class FeedbackWriter(Protocol):
    async def save_feedback(self, record: FeedbackRecord) -> None: ...


class AgentRunRequest(BaseModel):
    question: str


class AgentRunResponse(BaseModel):
    run_id: str
    answer: str
    events: list[AgentEvent]


class FeedbackRequest(BaseModel):
    run_id: str
    rating: str = Field(pattern="^(thumbs_up|thumbs_down)$")
    comment: str | None = None


class FeedbackResponse(BaseModel):
    status: str


def create_app(
    agent_runner: AgentRunner | None = None,
    feedback_repository: FeedbackWriter | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    if agent_runner is None:
        settings = settings or get_settings()
        configure_logging(settings.LOG_LEVEL)
        configure_tracing(settings)

    app = FastAPI(title="PaperGraph AI")
    instrument_prometheus(app)

    if settings:
        instrument_fastapi_app(app, settings)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/agent/runs")
    async def run_agent(request: AgentRunRequest) -> AgentRunResponse:
        runner = agent_runner or run_research_agent
        result = await runner(request.question)
        return AgentRunResponse.model_validate(result)

    @app.post("/feedback")
    async def create_feedback(request: FeedbackRequest) -> FeedbackResponse:
        repository = feedback_repository or get_feedback_repository()
        await repository.save_feedback(
            FeedbackRecord(
                run_id=request.run_id,
                rating=request.rating,
                comment=request.comment,
            )
        )
        return FeedbackResponse(status="ok")

    return app


@tracer.start_as_current_span("backend.run_research_agent")
async def run_research_agent(question: str) -> dict[str, Any]:
    settings = get_settings()
    events: list[AgentEvent] = []
    run_id = str(uuid4())
    start = monotonic()

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
        emit_event=events.append,
    )
    agent = ResearchAgent(
        tools=tools,
        model_name=settings.LLM_MODEL,
        api_key=settings.OPENAI_API_KEY,
        emit_event=events.append,
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
    return {"run_id": run_id, "answer": answer, "events": events}


@lru_cache(maxsize=1)
def get_feedback_repository() -> FeedbackRepository:
    settings = get_settings()
    return FeedbackRepository(db=get_postgres_engine(settings.POSTGRES_DATABASE_URL))


app = create_app()
