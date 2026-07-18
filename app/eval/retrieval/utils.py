from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from app.clients.openalex import OpenAlexClient
from app.db.neo4j import get_neo4j_driver
from app.db.qdrant import get_qdrant_client
from app.eval.retrieval.ids import normalize_openalex_id
from app.eval.retrieval.models import EvaluationItem, EvaluationResult, QueryEvaluationResult
from app.eval.retrieval.protocols import Retriever
from app.eval.retrieval.retrievers import (
    graph_keyword_retriever,
    openalex_keyword_retriever,
    qdrant_vector_plus_graph_retriever,
    qdrant_vector_retriever,
)
from app.repositories.graph import GraphRepository
from app.repositories.vector import VectorRepository
from app.settings import get_settings


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


def relevance_list(
    expected_openalex_ids: list[str],
    retrieved_openalex_ids: list[str],
    k: int,
) -> list[int]:
    """Build the course-style relevance list for retrieved results.

    Args:
        expected_openalex_ids: Relevant OpenAlex IDs for the query.
        retrieved_openalex_ids: OpenAlex IDs returned by a retriever.
        k: Number of top retrieved items to score.

    Returns:
        List containing 1 for relevant hits and 0 for non-relevant hits.
    """

    expected = {normalize_openalex_id(openalex_id) for openalex_id in expected_openalex_ids}
    retrieved = [normalize_openalex_id(openalex_id) for openalex_id in retrieved_openalex_ids[:k]]
    return [1 if openalex_id in expected else 0 for openalex_id in retrieved]


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

    expected = {normalize_openalex_id(openalex_id) for openalex_id in expected_openalex_ids}
    retrieved = [normalize_openalex_id(openalex_id) for openalex_id in retrieved_openalex_ids[:k]]
    relevance = relevance_list(expected_openalex_ids, retrieved, k)

    reciprocal_rank = 0.0
    for index, is_relevant in enumerate(relevance, start=1):
        if is_relevant:
            reciprocal_rank = 1 / index
            break

    return {
        "hit_rate_at_k": 1.0 if any(relevance) else 0.0,
        "precision_at_k": sum(relevance) / k,
        "recall_at_k": sum(relevance) / len(expected) if expected else 0.0,
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
        Aggregated metrics and per-question relevance results.
    """

    query_results = []
    for item in dataset:
        retrieved = [
            normalize_openalex_id(openalex_id) for openalex_id in await retriever(item.question, k)
        ]
        metrics = calculate_metrics(item.expected_openalex_ids, retrieved, k)
        query_results.append(
            QueryEvaluationResult(
                approach=approach,
                question=item.question,
                expected_openalex_ids=item.expected_openalex_ids,
                retrieved_openalex_ids=retrieved[:k],
                relevance=relevance_list(item.expected_openalex_ids, retrieved, k),
                hit_rate_at_k=metrics["hit_rate_at_k"],
                precision_at_k=metrics["precision_at_k"],
                recall_at_k=metrics["recall_at_k"],
                mrr_at_k=metrics["mrr_at_k"],
            )
        )

    count = len(query_results)
    return EvaluationResult(
        approach=approach,
        hit_rate_at_k=sum(result.hit_rate_at_k for result in query_results) / count,
        precision_at_k=sum(result.precision_at_k for result in query_results) / count,
        recall_at_k=sum(result.recall_at_k for result in query_results) / count,
        mrr_at_k=sum(result.mrr_at_k for result in query_results) / count,
        queries=query_results,
    )


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
            approach="neo4j_graph",
            dataset=dataset,
            retriever=graph_keyword_retriever(graph_repository),
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


def best_result(results: list[EvaluationResult]) -> EvaluationResult:
    """Select the best retrieval approach by MRR, hit rate, recall, then precision.

    Args:
        results: Evaluation results to compare.

    Returns:
        Highest-ranked retrieval result.
    """

    return sorted(
        results,
        key=lambda result: (
            result.mrr_at_k,
            result.hit_rate_at_k,
            result.recall_at_k,
            result.precision_at_k,
        ),
        reverse=True,
    )[0]


def summary_to_dataframe(results: list[EvaluationResult]) -> pd.DataFrame:
    """Convert retrieval summary results into a pandas DataFrame.

    Args:
        results: Evaluation results to convert.

    Returns:
        DataFrame with one row per retrieval approach, sorted by best score.
    """

    dataframe = pd.DataFrame(
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
    return dataframe.sort_values(
        ["mrr@k", "hit_rate@k", "recall@k", "precision@k"],
        ascending=False,
    )


def details_to_dataframe(results: list[EvaluationResult]) -> pd.DataFrame:
    """Convert per-question retrieval details into a pandas DataFrame.

    Args:
        results: Evaluation results with per-query details.

    Returns:
        DataFrame with one row per approach/question pair.
    """

    rows = []
    for result in results:
        for query_result in result.queries:
            rows.append(
                {
                    "approach": query_result.approach,
                    "question": query_result.question,
                    "expected_openalex_ids": query_result.expected_openalex_ids,
                    "retrieved_openalex_ids": query_result.retrieved_openalex_ids,
                    "relevance": query_result.relevance,
                    "hit_rate@k": query_result.hit_rate_at_k,
                    "precision@k": query_result.precision_at_k,
                    "recall@k": query_result.recall_at_k,
                    "mrr@k": query_result.mrr_at_k,
                }
            )

    return pd.DataFrame(rows)


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

    best = best_result(results)
    summary = summary_to_dataframe(results)
    details = details_to_dataframe(results)

    match output_format:
        case "json":
            return json.dumps(
                {
                    "best_approach": best.approach,
                    "summary": summary.to_dict(orient="records"),
                    "details": details.to_dict(orient="records"),
                },
                indent=2,
            )
        case "markdown":
            return "\n\n".join(
                [
                    f"Best retrieval approach: `{best.approach}`",
                    "## Retrieval Evaluation Summary",
                    summary.to_markdown(index=False, floatfmt=".3f"),
                    "## Retrieval Evaluation Details",
                    details.to_markdown(index=False, floatfmt=".3f"),
                ]
            )
        case "text":
            return "\n\n".join(
                [
                    f"Best retrieval approach: {best.approach}",
                    "Retrieval Evaluation Summary",
                    summary.to_string(index=False, float_format=lambda value: f"{value:.3f}"),
                    "Retrieval Evaluation Details",
                    details.to_string(index=False),
                ]
            )
        case _:
            raise ValueError(f"Unsupported output format: {output_format}")
