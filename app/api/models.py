from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, Protocol

from pydantic import BaseModel, Field

from app.agents.research import AgentEvent
from app.repositories.feedback import FeedbackRecord

AgentRunner = Callable[[str], Awaitable[dict[str, Any]]]
AgentStreamRunner = Callable[[str], AsyncIterator[dict[str, Any]]]


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
