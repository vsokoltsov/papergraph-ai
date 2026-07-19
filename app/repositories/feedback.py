from __future__ import annotations

from dataclasses import dataclass

from opentelemetry import trace
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.feedback_schema import FEEDBACK_METADATA, agent_runs_table, feedback_table
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
        self.schema_ready = False

    @tracer.start_as_current_span("feedback.save_agent_run")
    async def save_agent_run(self, record: AgentRunRecord) -> None:
        await self.ensure_schema()
        statement = insert(agent_runs_table).values(
            run_id=record.run_id,
            question=record.question,
            answer=record.answer,
            approach=record.approach,
            prompt_tokens=record.prompt_tokens,
            completion_tokens=record.completion_tokens,
            total_tokens=record.total_tokens,
            duration_seconds=record.duration_seconds,
        )
        statement = statement.on_conflict_do_update(
            index_elements=[agent_runs_table.c.run_id],
            set_={
                "question": statement.excluded.question,
                "answer": statement.excluded.answer,
                "approach": statement.excluded.approach,
                "prompt_tokens": statement.excluded.prompt_tokens,
                "completion_tokens": statement.excluded.completion_tokens,
                "total_tokens": statement.excluded.total_tokens,
                "duration_seconds": statement.excluded.duration_seconds,
            },
        )

        async with self.db.begin() as connection:
            await connection.execute(statement)

    @tracer.start_as_current_span("feedback.save_feedback")
    async def save_feedback(self, record: FeedbackRecord) -> None:
        await self.ensure_schema()
        statement = feedback_table.insert().values(
            run_id=record.run_id,
            rating=record.rating,
            comment=record.comment,
        )

        async with self.db.begin() as connection:
            await connection.execute(statement)
        FEEDBACK_TOTAL.labels(rating=record.rating).inc()

    @tracer.start_as_current_span("feedback.ensure_schema")
    async def ensure_schema(self) -> None:
        if self.schema_ready:
            return

        async with self.db.begin() as connection:
            await connection.run_sync(FEEDBACK_METADATA.create_all)

        self.schema_ready = True
