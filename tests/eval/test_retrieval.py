from dataclasses import dataclass
from typing import Any

import pytest

from app.eval.retrieval.evaluate import (
    EvaluationItem,
    EvaluationResult,
    calculate_metrics,
    evaluate_retriever,
    normalize_openalex_id,
    qdrant_vector_plus_graph_retriever,
    render_results,
    results_to_dataframe,
)


def test_normalize_openalex_id_accepts_short_and_full_ids() -> None:
    assert normalize_openalex_id("W1") == "https://openalex.org/W1"
    assert normalize_openalex_id("https://openalex.org/W1") == "https://openalex.org/W1"


def test_calculate_metrics() -> None:
    metrics = calculate_metrics(
        expected_openalex_ids=["https://openalex.org/W1", "https://openalex.org/W2"],
        retrieved_openalex_ids=[
            "https://openalex.org/W3",
            "https://openalex.org/W1",
            "https://openalex.org/W4",
        ],
        k=3,
    )

    assert metrics == {
        "hit_rate_at_k": 1.0,
        "precision_at_k": 1 / 3,
        "recall_at_k": 1 / 2,
        "mrr_at_k": 1 / 2,
    }


@pytest.mark.asyncio
async def test_evaluate_retriever_averages_metrics() -> None:
    async def retriever(question: str, k: int) -> list[str]:
        assert k == 2
        return {
            "question 1": ["https://openalex.org/W1"],
            "question 2": ["https://openalex.org/W3"],
        }[question]

    result = await evaluate_retriever(
        approach="fake",
        dataset=[
            EvaluationItem(
                question="question 1",
                expected_openalex_ids=["https://openalex.org/W1"],
            ),
            EvaluationItem(
                question="question 2",
                expected_openalex_ids=["https://openalex.org/W2"],
            ),
        ],
        retriever=retriever,
        k=2,
    )

    assert result.approach == "fake"
    assert result.hit_rate_at_k == 0.5
    assert result.precision_at_k == 0.25
    assert result.recall_at_k == 0.5
    assert result.mrr_at_k == 0.5


@pytest.mark.asyncio
async def test_qdrant_vector_plus_graph_retriever_adds_references() -> None:
    retriever = qdrant_vector_plus_graph_retriever(
        vector_repository=FakeVectorRepository(),
        graph_repository=FakeGraphRepository(),
    )

    assert await retriever("graph rag", 2) == [
        "https://openalex.org/W1",
        "https://openalex.org/W2",
    ]


def test_results_to_dataframe() -> None:
    dataframe = results_to_dataframe([sample_result()])

    assert dataframe.to_dict(orient="records") == [
        {
            "approach": "fake",
            "hit_rate@k": 1,
            "precision@k": 0.5,
            "recall@k": 0.25,
            "mrr@k": 1,
        }
    ]


def test_render_results_as_text() -> None:
    output = render_results([sample_result()], output_format="text")

    assert "fake" in output
    assert "hit_rate@k" in output
    assert "0.500" in output


def test_render_results_as_markdown() -> None:
    output = render_results([sample_result()], output_format="markdown")

    assert "| approach" in output
    assert "fake" in output


def test_render_results_as_json() -> None:
    output = render_results([sample_result()], output_format="json")

    assert '"approach":"fake"' in output.replace(" ", "")


def sample_result() -> EvaluationResult:
    return EvaluationResult(
        approach="fake",
        hit_rate_at_k=1,
        precision_at_k=0.5,
        recall_at_k=0.25,
        mrr_at_k=1,
    )


@dataclass
class FakeVectorRepository:
    async def search_papers(self, query: str | list[float], limit: int = 5) -> list[dict[str, Any]]:
        assert query == "graph rag"
        assert limit == 2
        return [
            {
                "payload": {
                    "openalex_id": "https://openalex.org/W1",
                }
            }
        ]


@dataclass
class FakeGraphRepository:
    async def get_paper_context(self, openalex_ids: list[str]) -> list[dict]:
        assert openalex_ids == ["https://openalex.org/W1"]
        return [{"references": [{"openalex_id": "https://openalex.org/W2"}]}]
