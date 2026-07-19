from __future__ import annotations

from dataclasses import dataclass

from opentelemetry import trace
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.metrics import FEEDBACK_TOTAL

tracer = trace.get_tracer(__name__)


@dataclass(frozen=True)
class AgentRunRecord:
    run_id: str
    question: str
    answer: str
    approach: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    duration_seconds: float | None = None


@dataclass(frozen=True)
class FeedbackRecord:
    run_id: str
    rating: str
    comment: str | None = None


class FeedbackRepository:
    def __init__(self, db: AsyncEngine) -> None:
        self.db = db

    @tracer.start_as_current_span("feedback.save_agent_run")
    async def save_agent_run(self, record: AgentRunRecord) -> None:
        async with self.db.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO agent_runs (
                        run_id,
                        question,
                        answer,
                        approach,
                        prompt_tokens,
                        completion_tokens,
                        total_tokens,
                        duration_seconds
                    )
                    VALUES (
                        :run_id,
                        :question,
                        :answer,
                        :approach,
                        :prompt_tokens,
                        :completion_tokens,
                        :total_tokens,
                        :duration_seconds
                    )
                    ON CONFLICT (run_id) DO UPDATE SET
                        question = EXCLUDED.question,
                        answer = EXCLUDED.answer,
                        approach = EXCLUDED.approach,
                        prompt_tokens = EXCLUDED.prompt_tokens,
                        completion_tokens = EXCLUDED.completion_tokens,
                        total_tokens = EXCLUDED.total_tokens,
                        duration_seconds = EXCLUDED.duration_seconds
                    """
                ),
                {
                    "run_id": record.run_id,
                    "question": record.question,
                    "answer": record.answer,
                    "approach": record.approach,
                    "prompt_tokens": record.prompt_tokens,
                    "completion_tokens": record.completion_tokens,
                    "total_tokens": record.total_tokens,
                    "duration_seconds": record.duration_seconds,
                },
            )

    @tracer.start_as_current_span("feedback.save_feedback")
    async def save_feedback(self, record: FeedbackRecord) -> None:
        async with self.db.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO feedback (run_id, rating, comment)
                    VALUES (:run_id, :rating, :comment)
                    """
                ),
                {
                    "run_id": record.run_id,
                    "rating": record.rating,
                    "comment": record.comment,
                },
            )
        FEEDBACK_TOTAL.labels(rating=record.rating).inc()
