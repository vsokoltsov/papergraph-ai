from collections.abc import AsyncIterator

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.api.lifespan import (
    get_feedback_repository,
    run_openalex_ingestion,
    run_research_agent,
    run_research_agent_stream,
)
from app.api.models import (
    AgentRunRequest,
    AgentRunResponse,
    AgentStreamRunner,
    FeedbackRequest,
    FeedbackResponse,
    OpenAlexIngestionRequest,
    OpenAlexIngestionResponse,
)
from app.repositories.feedback import FeedbackRecord

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/agent/runs")
async def run_agent(request: AgentRunRequest, app_request: Request) -> AgentRunResponse:
    runner = app_request.app.state.agent_runner or run_research_agent
    result = await runner(request.question)
    return AgentRunResponse.model_validate(result)


@router.post("/agent/runs/stream")
async def stream_agent(request: AgentRunRequest, app_request: Request) -> StreamingResponse:
    runner = app_request.app.state.agent_stream_runner or run_research_agent_stream
    return StreamingResponse(
        run_research_agent_sse(runner, request.question),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/feedback")
async def create_feedback(request: FeedbackRequest, app_request: Request) -> FeedbackResponse:
    repository = app_request.app.state.feedback_repository or get_feedback_repository()
    await repository.save_feedback(
        FeedbackRecord(
            run_id=request.run_id,
            rating=request.rating,
            comment=request.comment,
        )
    )
    return FeedbackResponse(status="ok")


@router.post("/ingestions/openalex")
async def ingest_openalex(
    request: OpenAlexIngestionRequest,
    app_request: Request,
    authorization: str | None = Header(default=None),
) -> OpenAlexIngestionResponse:
    settings = app_request.app.state.settings
    if settings.INGESTION_API_TOKEN:
        expected = f"Bearer {settings.INGESTION_API_TOKEN}"
        if authorization != expected:
            raise HTTPException(status_code=401, detail="Invalid ingestion token")

    runner = app_request.app.state.ingestion_runner or run_openalex_ingestion
    result = await runner(
        request.keyword,
        request.limit,
        request.from_year,
        request.dlt_output_dir,
    )
    return OpenAlexIngestionResponse.model_validate(result.__dict__)


async def run_research_agent_sse(
    runner: AgentStreamRunner,
    question: str,
) -> AsyncIterator[str]:
    from app.api.lifespan import stream_sse

    async for event in stream_sse(runner(question)):
        yield event
