from __future__ import annotations

from typing import Any, Protocol

from app.eval.llm.models import (
    AgentAnswerRecord,
    AgentEvaluation,
)


class AgentRunner(Protocol):
    """Interface for running the application agent during evaluation."""

    async def run(self, question: str) -> dict[str, Any]: ...


class LLMJudge(Protocol):
    """Interface for judging generated agent answers."""

    async def evaluate(self, record: AgentAnswerRecord) -> AgentEvaluation: ...
