from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI
from opentelemetry import trace
from pydantic import BaseModel

from app.agents.research import AgentEvent, ResearchAgent, create_research_tools
from app.clients.openalex import OpenAlexClient
from app.db.neo4j import get_neo4j_driver
from app.db.qdrant import get_qdrant_client
from app.logging import configure_logging
from app.repositories.graph import GraphRepository
from app.repositories.vector import VectorRepository
from app.services.papers import PapersService
from app.settings import Settings, get_settings
from app.tracing import configure_tracing, instrument_fastapi_app

tracer = trace.get_tracer(__name__)
AgentRunner = Callable[[str], Awaitable[dict[str, Any]]]


class AgentRunRequest(BaseModel):
    question: str


class AgentRunResponse(BaseModel):
    answer: str
    events: list[AgentEvent]


def create_app(
    agent_runner: AgentRunner | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    if agent_runner is None:
        settings = settings or get_settings()
        configure_logging(settings.LOG_LEVEL)
        configure_tracing(settings)

    app = FastAPI(title="PaperGraph AI")

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

    return app


@tracer.start_as_current_span("backend.run_research_agent")
async def run_research_agent(question: str) -> dict[str, Any]:
    settings = get_settings()
    events: list[AgentEvent] = []

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
    return {"answer": answer, "events": events}


app = create_app()
