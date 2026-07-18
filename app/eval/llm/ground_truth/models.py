from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field


@dataclass
class SourceDocument:
    """Document used as source material for LLM ground-truth generation.

    Attributes:
        document: Stable document identifier, usually the OpenAlex ID.
        title: Paper title.
        abstract: Paper abstract or other source text.
    """

    document: str
    title: str
    abstract: str


class GeneratedQuestion(BaseModel):
    """Single generated ground-truth question and answer.

    Attributes:
        question: Evaluation question generated from a source document.
        answer_orig: Ground-truth answer based only on the source document.
    """

    question: str = Field(description="A user-style research question.")
    answer_orig: str = Field(description="Ground-truth answer based only on the source document.")


class GeneratedQuestions(BaseModel):
    """Structured response containing generated evaluation examples.

    Attributes:
        questions: Generated question and answer pairs.
    """

    questions: list[GeneratedQuestion] = Field(
        description="Generated evaluation questions with ground-truth answers."
    )
