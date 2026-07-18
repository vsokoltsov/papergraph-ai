from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from app.eval.llm.ground_truth.generator import ground_truth_instructions, ground_truth_prompt
from app.eval.llm.ground_truth.models import GeneratedQuestion, SourceDocument
from app.eval.llm.ground_truth.utils import (
    document_from_payload,
    generate_ground_truth,
    load_documents_from_json,
    load_documents_from_qdrant,
    payload_has_source_text,
    save_dataset,
)


def test_document_from_payload_uses_openalex_id() -> None:
    document = document_from_payload(
        {
            "openalex_id": "https://openalex.org/W1",
            "title": "Graph RAG",
            "abstract": "Graph retrieval augmented generation.",
        }
    )

    assert document == SourceDocument(
        document="https://openalex.org/W1",
        title="Graph RAG",
        abstract="Graph retrieval augmented generation.",
    )


def test_payload_has_source_text_requires_title_and_abstract() -> None:
    assert payload_has_source_text({"title": "Graph RAG", "abstract": "Text"})
    assert not payload_has_source_text({"title": "Graph RAG"})
    assert not payload_has_source_text({"abstract": "Text"})


def test_ground_truth_prompt_contains_document_fields() -> None:
    prompt = ground_truth_prompt(
        document=SourceDocument(
            document="https://openalex.org/W1",
            title="Graph RAG",
            abstract="Graph retrieval augmented generation.",
        ),
        questions_per_document=2,
    )

    assert "Generate 2 evaluation question-answer pairs." in prompt
    assert "https://openalex.org/W1" in prompt
    assert "Graph RAG" in prompt


def test_ground_truth_instructions_focus_on_knowledge_graph_rag() -> None:
    instructions = ground_truth_instructions()

    assert "knowledge-graph-enhanced retrieval augmented generation" in instructions
    assert "other than" in instructions
    assert "retrieval augmented generation" in instructions


def test_load_documents_from_json(tmp_path: Path) -> None:
    input_path = tmp_path / "documents.json"
    input_path.write_text(
        """
        [
          {
            "openalex_id": "https://openalex.org/W1",
            "title": "Graph RAG",
            "abstract": "Graph retrieval augmented generation."
          },
          {
            "openalex_id": "https://openalex.org/W2",
            "title": "Vector Search",
            "abstract": "Semantic retrieval."
          }
        ]
        """
    )

    documents = load_documents_from_json(path=input_path, limit=1)

    assert documents == [
        SourceDocument(
            document="https://openalex.org/W1",
            title="Graph RAG",
            abstract="Graph retrieval augmented generation.",
        )
    ]


@pytest.mark.asyncio
async def test_load_documents_from_qdrant_uses_payloads_with_source_text() -> None:
    documents = await load_documents_from_qdrant(
        client=FakeQdrantClient(),
        collection_name="papers",
        limit=2,
    )

    assert documents == [
        SourceDocument(
            document="https://openalex.org/W1",
            title="Graph RAG",
            abstract="Graph retrieval augmented generation.",
        )
    ]


@pytest.mark.asyncio
async def test_generate_ground_truth_creates_dataset_rows() -> None:
    dataset = await generate_ground_truth(
        documents=[
            SourceDocument(
                document="https://openalex.org/W1",
                title="Graph RAG",
                abstract="Graph retrieval augmented generation.",
            )
        ],
        generator=FakeGroundTruthGenerator(),
        questions_per_document=2,
    )

    assert dataset == [
        {
            "question": "What does Graph RAG combine?",
            "answer_orig": "It combines graph context with retrieval augmented generation.",
            "document": "https://openalex.org/W1",
        }
    ]


def test_save_dataset_writes_json(tmp_path: Path) -> None:
    output_path = tmp_path / "dataset.json"

    save_dataset(
        dataset=[
            {
                "question": "What does Graph RAG combine?",
                "answer_orig": "It combines graph context with retrieval augmented generation.",
                "document": "https://openalex.org/W1",
            }
        ],
        output_path=output_path,
    )

    assert '"question": "What does Graph RAG combine?"' in output_path.read_text()


@dataclass
class FakePoint:
    payload: dict[str, Any] | None


@dataclass
class FakeQdrantClient:
    async def scroll(
        self,
        collection_name: str,
        scroll_filter: Any | None,
        limit: int,
        with_payload: bool,
        with_vectors: bool,
    ) -> tuple[list[FakePoint], None]:
        assert collection_name == "papers"
        assert scroll_filter is None
        assert limit == 2
        assert with_payload
        assert not with_vectors
        return (
            [
                FakePoint(
                    payload={
                        "openalex_id": "https://openalex.org/W1",
                        "title": "Graph RAG",
                        "abstract": "Graph retrieval augmented generation.",
                    }
                ),
                FakePoint(payload={"title": "Missing Abstract"}),
            ],
            None,
        )


@dataclass
class FakeGroundTruthGenerator:
    async def generate(
        self,
        document: SourceDocument,
        questions_per_document: int,
    ) -> list[GeneratedQuestion]:
        assert document.document == "https://openalex.org/W1"
        assert questions_per_document == 2
        return [
            GeneratedQuestion(
                question="What does Graph RAG combine?",
                answer_orig="It combines graph context with retrieval augmented generation.",
            )
        ]
