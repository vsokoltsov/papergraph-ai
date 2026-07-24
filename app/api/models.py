from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, Protocol

from pydantic import BaseModel, Field

from app.agents.research import AgentEvent
from app.ingestion.models import OpenAlexIngestionResult
from app.repositories.feedback import FeedbackRecord

AgentRunner = Callable[[str], Awaitable[dict[str, Any]]]
AgentStreamRunner = Callable[[str], AsyncIterator[dict[str, Any]]]
IngestionRunner = Callable[
    [str, int, int | None, str | None],
    Awaitable[OpenAlexIngestionResult],
]


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


class OpenAlexIngestionRequest(BaseModel):
    keyword: str
    limit: int = Field(default=10, ge=1, le=100)
    from_year: int | None = Field(default=None, ge=1900)
    dlt_output_dir: str | None = None


class OpenAlexIngestionResponse(BaseModel):
    query: str
    staged_records: int
    inserted_articles: int
    dlt_output_dir: str
    dlt_load_info: str
