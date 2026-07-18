from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import pandas as pd

from app.clients.openalex import OpenAlexClient
from app.db.neo4j import get_neo4j_driver
from app.db.qdrant import get_qdrant_client
from app.repositories.graph import GraphRepository
from app.repositories.vector import VectorRepository
from app.settings import get_settings

OPENALEX_URL_PREFIX = "https://openalex.org/"
Retriever = Callable[[str, int], Awaitable[list[str]]]


class VectorSearchRepository(Protocol):
    """Repository interface for vector-based paper search."""

    async def search_papers(
        self,
        query: str | list[float],
        limit: int = 5,
    ) -> list[dict[str, Any]]: ...


class GraphContextRepository(Protocol):
    """Repository interface for fetching paper graph context."""

    async def get_paper_context(self, openalex_ids: list[str]) -> list[dict]: ...


@dataclass
class EvaluationItem:
    """Single retrieval evaluation example.

    Attributes:
        question: User-style search question.
        expected_openalex_ids: OpenAlex work IDs that should be retrieved.
    """

    question: str
    expected_openalex_ids: list[str]


@dataclass
class EvaluationResult:
    """Aggregated retrieval metrics for one retrieval approach.

    Attributes:
        approach: Name of the evaluated retrieval approach.
        hit_rate_at_k: Share of questions with at least one expected result in top-k.
        precision_at_k: Share of top-k retrieved results that are expected.
        recall_at_k: Share of expected results retrieved in top-k.
        mrr_at_k: Mean reciprocal rank of the first expected result.
    """

    approach: str
    hit_rate_at_k: float
    precision_at_k: float
    recall_at_k: float
    mrr_at_k: float


def normalize_openalex_id(openalex_id: str) -> str:
    """Return a full OpenAlex URL for short or full work IDs.

    Args:
        openalex_id: Short ID like `W123` or full URL like `https://openalex.org/W123`.

    Returns:
        Full OpenAlex work URL.
    """

    if openalex_id.startswith(OPENALEX_URL_PREFIX):
        return openalex_id

    return f"{OPENALEX_URL_PREFIX}{openalex_id}"


def load_dataset(path: Path) -> list[EvaluationItem]:
    """Load retrieval evaluation examples from a JSON file.

    Args:
        path: Path to the dataset JSON file.

    Returns:
        Parsed evaluation examples with normalized expected OpenAlex IDs.
    """

    data = json.loads(path.read_text())
    return [
        EvaluationItem(
            question=item["question"],
            expected_openalex_ids=[
                normalize_openalex_id(openalex_id) for openalex_id in item["expected_openalex_ids"]
            ],
        )
        for item in data
    ]


def calculate_metrics(
    expected_openalex_ids: list[str],
    retrieved_openalex_ids: list[str],
    k: int,
) -> dict[str, float]:
    """Calculate top-k retrieval metrics for one query.

    Args:
        expected_openalex_ids: Relevant OpenAlex IDs for the query.
        retrieved_openalex_ids: OpenAlex IDs returned by a retriever.
        k: Number of top retrieved items to score.

    Returns:
        Dictionary with hit rate, precision, recall, and MRR values.
    """

    expected = set(expected_openalex_ids)
    retrieved = [normalize_openalex_id(openalex_id) for openalex_id in retrieved_openalex_ids[:k]]
    matched = [openalex_id for openalex_id in retrieved if openalex_id in expected]

    reciprocal_rank = 0.0
    for index, openalex_id in enumerate(retrieved, start=1):
        if openalex_id in expected:
            reciprocal_rank = 1 / index
            break

    return {
        "hit_rate_at_k": 1.0 if matched else 0.0,
        "precision_at_k": len(matched) / k,
        "recall_at_k": len(matched) / len(expected) if expected else 0.0,
        "mrr_at_k": reciprocal_rank,
    }


async def evaluate_retriever(
    approach: str,
    dataset: list[EvaluationItem],
    retriever: Retriever,
    k: int,
) -> EvaluationResult:
    """Evaluate one retriever against a retrieval dataset.

    Args:
        approach: Display name for the retrieval approach.
        dataset: Evaluation examples.
        retriever: Async function returning OpenAlex IDs for a question.
        k: Number of top retrieved items to score.

    Returns:
        Aggregated metrics for the retriever.
    """

    totals = {
        "hit_rate_at_k": 0.0,
        "precision_at_k": 0.0,
        "recall_at_k": 0.0,
        "mrr_at_k": 0.0,
    }

    for item in dataset:
        retrieved = await retriever(item.question, k)
        metrics = calculate_metrics(item.expected_openalex_ids, retrieved, k)
        for metric_name, metric_value in metrics.items():
            totals[metric_name] += metric_value

    count = len(dataset)
    return EvaluationResult(
        approach=approach,
        hit_rate_at_k=totals["hit_rate_at_k"] / count,
        precision_at_k=totals["precision_at_k"] / count,
        recall_at_k=totals["recall_at_k"] / count,
        mrr_at_k=totals["mrr_at_k"] / count,
    )


def openalex_keyword_retriever(client: OpenAlexClient) -> Retriever:
    """Create a retriever that uses OpenAlex keyword search.

    Args:
        client: OpenAlex API client.

    Returns:
        Async retriever function.
    """

    async def retrieve(question: str, k: int) -> list[str]:
        """Retrieve OpenAlex IDs from OpenAlex keyword search."""

        articles = await client.get_articles(query=question, limit=k)
        return [article.id for article in articles]

    return retrieve


def qdrant_vector_retriever(repository: VectorSearchRepository) -> Retriever:
    """Create a retriever that uses Qdrant vector search.

    Args:
        repository: Vector repository with a search method.

    Returns:
        Async retriever function.
    """

    async def retrieve(question: str, k: int) -> list[str]:
        """Retrieve OpenAlex IDs from Qdrant payloads."""

        results = await repository.search_papers(query=question, limit=k)
        return [
            result["payload"]["openalex_id"]
            for result in results
            if result.get("payload", {}).get("openalex_id")
        ]

    return retrieve


def qdrant_vector_plus_graph_retriever(
    vector_repository: VectorSearchRepository,
    graph_repository: GraphContextRepository,
) -> Retriever:
    """Create a retriever that combines vector search with graph expansion.

    The approach starts from Qdrant vector hits, then adds cited papers from Neo4j
    graph context.

    Args:
        vector_repository: Vector repository used for initial semantic search.
        graph_repository: Graph repository used for citation expansion.

    Returns:
        Async retriever function.
    """

    async def retrieve(question: str, k: int) -> list[str]:
        """Retrieve OpenAlex IDs from vector hits plus graph references."""

        vector_results = await qdrant_vector_retriever(vector_repository)(question, k)
        graph_context = await graph_repository.get_paper_context(vector_results)

        ids = list(vector_results)
        for context in graph_context:
            for reference in context.get("references", []):
                openalex_id = reference.get("openalex_id")
                if openalex_id and openalex_id not in ids:
                    ids.append(openalex_id)

        return ids[:k]

    return retrieve


async def run_evaluation(dataset_path: Path, k: int) -> list[EvaluationResult]:
    """Run all configured retrieval evaluations.

    Args:
        dataset_path: Path to the retrieval evaluation dataset.
        k: Number of top retrieved items to score.

    Returns:
        Aggregated metrics for each retrieval approach.
    """

    settings = get_settings()
    dataset = load_dataset(dataset_path)
    openalex_client = OpenAlexClient(api_key=settings.OPENALEX_API_KEY)
    vector_repository = VectorRepository(
        db=get_qdrant_client(url=settings.QDRANT_URL),
        collection_name=settings.QDRANT_COLLECTION_NAME,
    )
    graph_driver = get_neo4j_driver(
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD,
    )
    graph_repository = GraphRepository(db=graph_driver)

    return [
        await evaluate_retriever(
            approach="openalex_keyword",
            dataset=dataset,
            retriever=openalex_keyword_retriever(openalex_client),
            k=k,
        ),
        await evaluate_retriever(
            approach="qdrant_vector",
            dataset=dataset,
            retriever=qdrant_vector_retriever(vector_repository),
            k=k,
        ),
        await evaluate_retriever(
            approach="qdrant_vector_plus_graph",
            dataset=dataset,
            retriever=qdrant_vector_plus_graph_retriever(
                vector_repository=vector_repository,
                graph_repository=graph_repository,
            ),
            k=k,
        ),
    ]


def results_to_dataframe(results: list[EvaluationResult]) -> pd.DataFrame:
    """Convert retrieval evaluation results into a pandas DataFrame.

    Args:
        results: Evaluation results to convert.

    Returns:
        DataFrame with one row per retrieval approach.
    """

    return pd.DataFrame(
        [
            {
                "approach": result.approach,
                "hit_rate@k": result.hit_rate_at_k,
                "precision@k": result.precision_at_k,
                "recall@k": result.recall_at_k,
                "mrr@k": result.mrr_at_k,
            }
            for result in results
        ]
    )


def render_results(results: list[EvaluationResult], output_format: str = "text") -> str:
    """Render retrieval evaluation results for CLI output.

    Args:
        results: Evaluation results to render.
        output_format: One of `text`, `markdown`, or `json`.

    Returns:
        Rendered evaluation output.

    Raises:
        ValueError: If output_format is unsupported.
    """

    dataframe = results_to_dataframe(results)

    match output_format:
        case "json":
            return str(dataframe.to_json(orient="records", indent=2))
        case "markdown":
            return dataframe.to_markdown(index=False, floatfmt=".3f")
        case "text":
            return dataframe.to_string(index=False, float_format=lambda value: f"{value:.3f}")
        case _:
            raise ValueError(f"Unsupported output format: {output_format}")


async def main() -> None:
    """Parse CLI arguments and print retrieval evaluation results."""

    parser = argparse.ArgumentParser(description="Evaluate retrieval approaches.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path(__file__).with_name("dataset.json"),
    )
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument(
        "--output-format",
        choices=["text", "markdown", "json"],
        default="text",
    )
    args = parser.parse_args()

    results = await run_evaluation(dataset_path=args.dataset, k=args.k)
    print(render_results(results, output_format=args.output_format))


if __name__ == "__main__":
    asyncio.run(main())
