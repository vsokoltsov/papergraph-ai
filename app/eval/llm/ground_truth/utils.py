from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.db.qdrant import get_qdrant_client
from app.eval.llm.ground_truth.models import SourceDocument
from app.eval.llm.ground_truth.protocols import GroundTruthGenerator
from app.settings import get_settings


def load_documents_from_json(path: Path, limit: int) -> list[SourceDocument]:
    """Load source documents from a JSON file.

    The file can contain either source documents with `document`, `title`, and `abstract`
    fields, or existing Qdrant-style payloads with `openalex_id`, `title`, and `abstract`.

    Args:
        path: Path to the JSON source file.
        limit: Maximum number of source documents to load.

    Returns:
        Source documents suitable for ground-truth generation.
    """

    data = json.loads(path.read_text())
    return [document_from_payload(item) for item in data[:limit]]


async def load_documents_from_qdrant(
    client: Any,
    collection_name: str,
    limit: int,
) -> list[SourceDocument]:
    """Load source documents from Qdrant payloads.

    Args:
        client: Qdrant async client.
        collection_name: Qdrant collection containing paper payloads.
        limit: Maximum number of source documents to load.

    Returns:
        Source documents created from Qdrant point payloads.
    """

    points, _ = await client.scroll(
        collection_name=collection_name,
        scroll_filter=None,
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )

    return [
        document_from_payload(point.payload or {})
        for point in points
        if payload_has_source_text(point.payload or {})
    ]


def payload_has_source_text(payload: dict[str, Any]) -> bool:
    """Check whether a payload has enough text for question generation.

    Args:
        payload: Source payload from JSON or Qdrant.

    Returns:
        True when the payload contains title and abstract text.
    """

    return bool(payload.get("title")) and bool(payload.get("abstract"))


def document_from_payload(payload: dict[str, Any]) -> SourceDocument:
    """Convert a paper payload into a source document.

    Args:
        payload: Source payload from JSON or Qdrant.

    Returns:
        Normalized source document.
    """

    document = payload.get("document") or payload.get("openalex_id") or payload.get("id")
    return SourceDocument(
        document=str(document),
        title=str(payload["title"]),
        abstract=str(payload["abstract"]),
    )


async def generate_ground_truth(
    documents: list[SourceDocument],
    generator: GroundTruthGenerator,
    questions_per_document: int,
) -> list[dict[str, str]]:
    """Generate LLM evaluation dataset rows from source documents.

    Args:
        documents: Source documents to use as answer material.
        generator: Ground-truth generator implementation.
        questions_per_document: Number of examples to generate per document.

    Returns:
        Dataset rows with `question`, `answer_orig`, and `document`.
    """

    dataset = []
    for document in documents:
        generated_questions = await generator.generate(
            document=document,
            questions_per_document=questions_per_document,
        )
        for generated_question in generated_questions:
            dataset.append(
                {
                    "question": generated_question.question,
                    "answer_orig": generated_question.answer_orig,
                    "document": document.document,
                }
            )

    return dataset


def save_dataset(dataset: list[dict[str, str]], output_path: Path) -> None:
    """Save generated ground-truth examples as JSON.

    Args:
        dataset: Generated dataset rows.
        output_path: Destination JSON path.
    """

    output_path.write_text(json.dumps(dataset, indent=2, ensure_ascii=False))


async def load_source_documents(
    source: str, input_path: Path | None, limit: int
) -> list[SourceDocument]:
    """Load source documents from the configured source.

    Args:
        source: Source type, either `qdrant` or `json`.
        input_path: JSON input path when source is `json`.
        limit: Maximum number of source documents.

    Returns:
        Loaded source documents.

    Raises:
        ValueError: If the source type is unsupported or required input is missing.
    """

    match source:
        case "qdrant":
            settings = get_settings()
            return await load_documents_from_qdrant(
                client=get_qdrant_client(url=settings.QDRANT_URL),
                collection_name=settings.QDRANT_COLLECTION_NAME,
                limit=limit,
            )
        case "json":
            if input_path is None:
                raise ValueError("--input is required when --source=json")
            return load_documents_from_json(path=input_path, limit=limit)
        case _:
            raise ValueError(f"Unsupported source: {source}")
