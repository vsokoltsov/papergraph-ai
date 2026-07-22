"""Models used by the PaperGraph research agent."""

from typing import Any

from langchain_core.messages import BaseMessage
from typing_extensions import TypedDict

AgentEvent = dict[str, Any]


class ResearchGraphState(TypedDict, total=False):
    """State passed between LangGraph research workflow nodes.

    Attributes:
        question: Original user question.
        rewritten_query: Retrieval-oriented query derived from the question.
        retrieved_documents: Candidate papers retrieved from vector or graph stores.
        ranked_documents: Candidate papers after deterministic reranking.
        graph_context: Neo4j context for selected papers.
        answer: Final generated answer.
        messages: LLM messages used for answer generation.
    """

    question: str
    rewritten_query: str
    retrieved_documents: list[dict[str, Any]]
    ranked_documents: list[dict[str, Any]]
    graph_context: list[dict[str, Any]]
    answer: str
    messages: list[BaseMessage]
