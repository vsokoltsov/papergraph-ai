from __future__ import annotations

from dataclasses import dataclass


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
class QueryEvaluationResult:
    """Retrieval metrics for one question and one approach.

    Attributes:
        approach: Name of the retrieval approach.
        question: Evaluated question.
        expected_openalex_ids: Relevant OpenAlex IDs for the question.
        retrieved_openalex_ids: OpenAlex IDs returned by the retriever.
        relevance: Course-style relevance list, where 1 means relevant and 0 means not relevant.
        hit_rate_at_k: 1 when at least one expected item is retrieved in top-k.
        precision_at_k: Share of top-k retrieved results that are expected.
        recall_at_k: Share of expected results retrieved in top-k.
        mrr_at_k: Reciprocal rank of the first expected result.
    """

    approach: str
    question: str
    expected_openalex_ids: list[str]
    retrieved_openalex_ids: list[str]
    relevance: list[int]
    hit_rate_at_k: float
    precision_at_k: float
    recall_at_k: float
    mrr_at_k: float


@dataclass
class EvaluationResult:
    """Aggregated retrieval metrics for one retrieval approach.

    Attributes:
        approach: Name of the evaluated retrieval approach.
        hit_rate_at_k: Share of questions with at least one expected result in top-k.
        precision_at_k: Share of top-k retrieved results that are expected.
        recall_at_k: Share of expected results retrieved in top-k.
        mrr_at_k: Mean reciprocal rank of the first expected result.
        queries: Per-question retrieval evaluation results.
    """

    approach: str
    hit_rate_at_k: float
    precision_at_k: float
    recall_at_k: float
    mrr_at_k: float
    queries: list[QueryEvaluationResult]
