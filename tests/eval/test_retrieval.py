from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from app.eval.retrieval import evaluate
from app.eval.retrieval.evaluate import (
    EvaluationItem,
    EvaluationResult,
    QueryEvaluationResult,
    best_result,
    calculate_metrics,
    details_to_dataframe,
    evaluate_retriever,
    graph_keyword_retriever,
    load_dataset,
    normalize_openalex_id,
    qdrant_vector_plus_graph_retriever,
    relevance_list,
    render_results,
    summary_to_dataframe,
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


def test_relevance_list() -> None:
    assert relevance_list(
        expected_openalex_ids=["https://openalex.org/W1"],
        retrieved_openalex_ids=["W2", "W1"],
        k=2,
    ) == [0, 1]


def test_committed_dataset_contains_paraphrase_and_multi_document_queries() -> None:
    dataset = [
        item
        for item in load_dataset(
            Path(__file__).parents[2] / "app" / "eval" / "retrieval" / "dataset.json"
        )
    ]

    assert len(dataset) >= 10
    assert any(len(item.expected_openalex_ids) > 1 for item in dataset)
    assert any("hallucinations" in item.question for item in dataset)
    assert any(
        "connected to clinical or biomedical applications" in item.question for item in dataset
    )


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
    assert result.queries[0].relevance == [1]
    assert result.queries[1].relevance == [0]


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


@pytest.mark.asyncio
async def test_graph_keyword_retriever_returns_paper_ids() -> None:
    retriever = graph_keyword_retriever(FakeGraphRepository())

    assert await retriever("graph rag", 2) == ["https://openalex.org/W3"]


def test_summary_to_dataframe_sorts_by_best_metrics() -> None:
    dataframe = summary_to_dataframe(
        [
            sample_result(approach="lower", mrr_at_k=0.5),
            sample_result(approach="higher", mrr_at_k=1.0),
        ]
    )

    assert dataframe["approach"].to_list() == ["higher", "lower"]


def test_details_to_dataframe() -> None:
    dataframe = details_to_dataframe([sample_result()])

    assert dataframe.to_dict(orient="records") == [
        {
            "approach": "fake",
            "question": "question",
            "expected_openalex_ids": ["https://openalex.org/W1"],
            "retrieved_openalex_ids": ["https://openalex.org/W1"],
            "relevance": [1],
            "hit_rate@k": 1,
            "precision@k": 0.5,
            "recall@k": 0.25,
            "mrr@k": 1,
        }
    ]


def test_best_result_uses_mrr_then_hit_rate() -> None:
    assert (
        best_result(
            [
                sample_result(approach="lower", mrr_at_k=0.5),
                sample_result(approach="higher", mrr_at_k=1.0),
            ]
        ).approach
        == "higher"
    )


def test_render_results_as_text() -> None:
    output = render_results([sample_result()], output_format="text")

    assert "fake" in output
    assert "Best retrieval approach: fake" in output
    assert "hit_rate@k" in output
    assert "0.500" in output


def test_render_results_as_markdown() -> None:
    output = render_results([sample_result()], output_format="markdown")

    assert "| approach" in output
    assert "Best retrieval approach: `fake`" in output
    assert "fake" in output


def test_render_results_as_json() -> None:
    output = render_results([sample_result()], output_format="json")

    assert '"best_approach": "fake"' in output
    assert '"approach":"fake"' in output.replace(" ", "")


@pytest.mark.asyncio
async def test_cli_writes_markdown_and_json_from_one_run(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    calls = 0

    async def fake_run_evaluation(dataset_path, k):
        nonlocal calls
        calls += 1
        assert dataset_path.name == "dataset.json"
        assert k == 5
        return [sample_result()]

    monkeypatch.setattr(evaluate, "run_evaluation", fake_run_evaluation)
    monkeypatch.setattr(
        "sys.argv",
        [
            "evaluate.py",
            "--dataset",
            "dataset.json",
            "--k",
            "5",
            "--output-format",
            "markdown",
            "--output-dir",
            str(tmp_path),
        ],
    )

    await evaluate.main()

    captured = capsys.readouterr()
    assert calls == 1
    assert "Best retrieval approach: `fake`" in captured.out
    assert "Best retrieval approach: `fake`" in (tmp_path / "retrieval-eval.md").read_text()
    assert '"best_approach": "fake"' in (tmp_path / "retrieval-eval.json").read_text()


def sample_result(approach: str = "fake", mrr_at_k: float = 1) -> EvaluationResult:
    return EvaluationResult(
        approach=approach,
        hit_rate_at_k=1,
        precision_at_k=0.5,
        recall_at_k=0.25,
        mrr_at_k=mrr_at_k,
        queries=[
            QueryEvaluationResult(
                approach=approach,
                question="question",
                expected_openalex_ids=["https://openalex.org/W1"],
                retrieved_openalex_ids=["https://openalex.org/W1"],
                relevance=[1],
                hit_rate_at_k=1,
                precision_at_k=0.5,
                recall_at_k=0.25,
                mrr_at_k=mrr_at_k,
            )
        ],
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
    async def search_papers(self, query: str, limit: int = 5) -> list[dict]:
        assert query == "graph rag"
        assert limit == 2
        return [{"paper": {"openalex_id": "W3"}}]

    async def get_paper_context(self, openalex_ids: list[str]) -> list[dict]:
        assert openalex_ids == ["https://openalex.org/W1"]
        return [{"references": [{"openalex_id": "https://openalex.org/W2"}]}]
