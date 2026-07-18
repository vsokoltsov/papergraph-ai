from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from app.eval.retrieval.ids import normalize_openalex_id
from app.eval.retrieval.models import EvaluationItem, EvaluationResult, QueryEvaluationResult
from app.eval.retrieval.retrievers import (
    graph_keyword_retriever,
    openalex_keyword_retriever,
    qdrant_vector_plus_graph_retriever,
    qdrant_vector_retriever,
)
from app.eval.retrieval.utils import (
    best_result,
    calculate_metrics,
    details_to_dataframe,
    evaluate_retriever,
    load_dataset,
    relevance_list,
    render_results,
    run_evaluation,
    summary_to_dataframe,
)

__all__ = [
    "EvaluationItem",
    "EvaluationResult",
    "QueryEvaluationResult",
    "best_result",
    "calculate_metrics",
    "details_to_dataframe",
    "evaluate_retriever",
    "graph_keyword_retriever",
    "load_dataset",
    "normalize_openalex_id",
    "openalex_keyword_retriever",
    "qdrant_vector_plus_graph_retriever",
    "qdrant_vector_retriever",
    "relevance_list",
    "render_results",
    "run_evaluation",
    "summary_to_dataframe",
]


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
