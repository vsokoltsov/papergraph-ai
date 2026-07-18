from typing import Protocol

from app.eval.llm.ground_truth.models import GeneratedQuestion, SourceDocument


class GroundTruthGenerator(Protocol):
    """Interface for generating ground-truth examples from source documents."""

    async def generate(
        self,
        document: SourceDocument,
        questions_per_document: int,
    ) -> list[GeneratedQuestion]: ...
