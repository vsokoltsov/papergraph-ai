"""LangGraph workflow for the PaperGraph research agent."""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, cast

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, StateGraph

from app.agents.models import ResearchGraphState
from app.agents.research_tools import rerank_documents, rewrite_search_query, to_json


@dataclass(frozen=True)
class ResearchGraphRuntime:
    """Runtime dependency container for LangGraph node functions.

    Attributes:
        tool_map: Mapping of enabled tool names to LangChain tools.
        llm: Chat model used for final answer generation.
        system_prompt: System prompt used by the answer node.
    """

    tool_map: dict[str, BaseTool]
    llm: Any
    system_prompt: str

    async def rewrite_query_node(self, state: ResearchGraphState) -> ResearchGraphState:
        """Rewrite the user question for retrieval.

        Args:
            state: Current workflow state.

        Returns:
            State update containing the rewritten query.
        """

        return await rewrite_query_node(state=state, tool_map=self.tool_map)

    async def retrieve_documents_node(self, state: ResearchGraphState) -> ResearchGraphState:
        """Retrieve candidate documents from enabled retrieval tools.

        Args:
            state: Current workflow state.

        Returns:
            State update containing retrieved documents.
        """

        return await retrieve_documents_node(state=state, tool_map=self.tool_map)

    async def rerank_documents_node(self, state: ResearchGraphState) -> ResearchGraphState:
        """Rerank retrieved candidates before graph enrichment.

        Args:
            state: Current workflow state.

        Returns:
            State update containing ranked documents.
        """

        return await rerank_documents_node(state=state, tool_map=self.tool_map)

    async def graph_context_node(self, state: ResearchGraphState) -> ResearchGraphState:
        """Load graph context for selected papers.

        Args:
            state: Current workflow state.

        Returns:
            State update containing graph context.
        """

        return await graph_context_node(state=state, tool_map=self.tool_map)

    async def answer_node(self, state: ResearchGraphState) -> ResearchGraphState:
        """Generate the final answer from retrieved state.

        Args:
            state: Current workflow state.

        Returns:
            State update containing answer and LLM messages.
        """

        return await answer_node(
            state=state,
            llm=self.llm,
            system_prompt=self.system_prompt,
        )


def build_research_graph(
    tools: Sequence[BaseTool],
    llm: Any,
    system_prompt: str,
):
    """Build the explicit LangGraph research workflow.

    Args:
        tools: Tools available to the workflow.
        llm: Chat model used for final answer generation.
        system_prompt: System prompt for the final answer node.

    Returns:
        Compiled LangGraph workflow.
    """

    runtime = ResearchGraphRuntime(
        tool_map={tool.name: tool for tool in tools},
        llm=llm,
        system_prompt=system_prompt,
    )
    graph = StateGraph(cast(Any, ResearchGraphState))
    graph.add_node("rewrite_query", runtime.rewrite_query_node)
    graph.add_node("retrieve_documents", runtime.retrieve_documents_node)
    graph.add_node("rerank_documents", runtime.rerank_documents_node)
    graph.add_node("graph_context", runtime.graph_context_node)
    graph.add_node("answer", runtime.answer_node)

    # The workflow intentionally follows a fixed order to make agent behavior testable.
    graph.set_entry_point("rewrite_query")
    graph.add_edge("rewrite_query", "retrieve_documents")
    graph.add_edge("retrieve_documents", "rerank_documents")
    graph.add_edge("rerank_documents", "graph_context")
    graph.add_edge("graph_context", "answer")
    graph.add_edge("answer", END)
    return graph.compile()


async def rewrite_query_node(
    state: ResearchGraphState,
    tool_map: dict[str, BaseTool],
) -> ResearchGraphState:
    """Rewrite the user question for retrieval.

    Args:
        state: Current workflow state.
        tool_map: Mapping of enabled tool names to LangChain tools.

    Returns:
        State update containing the rewritten query.
    """

    question = state["question"]
    tool = tool_map.get("rewrite_search_query")
    if tool is None:
        return {"rewritten_query": rewrite_search_query(question)}

    rewritten_query = await tool.ainvoke({"question": question})
    return {"rewritten_query": str(rewritten_query)}


async def retrieve_documents_node(
    state: ResearchGraphState,
    tool_map: dict[str, BaseTool],
) -> ResearchGraphState:
    """Retrieve candidate documents from enabled retrieval tools.

    Args:
        state: Current workflow state.
        tool_map: Mapping of enabled tool names to LangChain tools.

    Returns:
        State update containing retrieved documents.
    """

    query = state.get("rewritten_query") or state["question"]
    documents: list[dict[str, Any]] = []

    # Prefer vector search for content evidence when it is enabled.
    vector_tool = tool_map.get("search_vector_database")
    if vector_tool is not None:
        documents.extend(await invoke_json_list_tool(vector_tool, {"query": query, "limit": 5}))

    # Graph-only evaluation exposes this tool without vector search.
    graph_tool = tool_map.get("search_graph_database")
    if vector_tool is None and graph_tool is not None:
        documents.extend(await invoke_json_list_tool(graph_tool, {"query": query, "limit": 5}))

    return {"retrieved_documents": documents}


async def rerank_documents_node(
    state: ResearchGraphState,
    tool_map: dict[str, BaseTool],
) -> ResearchGraphState:
    """Rerank retrieved candidates before graph enrichment.

    Args:
        state: Current workflow state.
        tool_map: Mapping of enabled tool names to LangChain tools.

    Returns:
        State update containing ranked documents.
    """

    documents = state.get("retrieved_documents", [])
    tool = tool_map.get("rerank_documents")
    if tool is None:
        ranked_documents = rerank_documents(state["question"], documents=documents, limit=5)
        return {"ranked_documents": ranked_documents}

    ranked_documents = await invoke_json_list_tool(
        tool,
        {
            "question": state["question"],
            "documents_json": to_json(documents),
            "limit": 5,
        },
    )
    return {"ranked_documents": ranked_documents}


async def graph_context_node(
    state: ResearchGraphState,
    tool_map: dict[str, BaseTool],
) -> ResearchGraphState:
    """Load graph context for selected papers.

    Args:
        state: Current workflow state.
        tool_map: Mapping of enabled tool names to LangChain tools.

    Returns:
        State update containing graph context.
    """

    tool = tool_map.get("get_graph_context")
    if tool is None:
        return {"graph_context": []}

    openalex_ids = extract_openalex_ids(state.get("ranked_documents", []))
    if not openalex_ids:
        return {"graph_context": []}

    graph_context = await invoke_json_list_tool(tool, {"openalex_ids": openalex_ids})
    return {"graph_context": graph_context}


async def answer_node(
    state: ResearchGraphState,
    llm: Any,
    system_prompt: str,
) -> ResearchGraphState:
    """Generate the final answer from retrieved state.

    Args:
        state: Current workflow state.
        llm: Chat model used for final answer generation.
        system_prompt: System prompt used for the answer.

    Returns:
        State update containing answer and LLM messages.
    """

    messages: list[BaseMessage] = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=build_answer_prompt(state)),
    ]
    response = await llm.ainvoke(messages)
    answer = message_content_to_text(response.content)
    return {"answer": answer, "messages": [*messages, response]}


async def invoke_json_list_tool(tool: BaseTool, arguments: dict[str, Any]) -> list[dict[str, Any]]:
    """Invoke a tool and parse a JSON list response.

    Args:
        tool: LangChain-compatible tool to invoke.
        arguments: Tool arguments.

    Returns:
        Parsed list of dictionary items. Malformed or non-list responses return an empty list.
    """

    result = await tool.ainvoke(arguments)
    try:
        parsed = json.loads(str(result))
    except json.JSONDecodeError:
        return []

    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, dict)]


def extract_openalex_ids(documents: list[dict[str, Any]]) -> list[str]:
    """Extract OpenAlex paper IDs from retrieved documents.

    Args:
        documents: Retrieved or ranked paper documents.

    Returns:
        Deduplicated OpenAlex IDs in ranking order.
    """

    openalex_ids: list[str] = []
    for document in documents:
        # Qdrant stores OpenAlex IDs in payload; Neo4j search stores them under paper.
        candidates = [
            document.get("openalex_id"),
            _nested_value(document, "payload", "openalex_id"),
            _nested_value(document, "paper", "openalex_id"),
        ]
        for candidate in candidates:
            if candidate and str(candidate) not in openalex_ids:
                openalex_ids.append(str(candidate))

    return openalex_ids


def build_answer_prompt(state: ResearchGraphState) -> str:
    """Build the final answer prompt from workflow state.

    Args:
        state: Final workflow state before answer generation.

    Returns:
        User-facing answer prompt containing retrieved evidence.
    """

    return (
        f"Question:\n{state['question']}\n\n"
        f"Rewritten retrieval query:\n{state.get('rewritten_query', '')}\n\n"
        f"Reranked retrieved papers JSON:\n{to_json(state.get('ranked_documents', []))}\n\n"
        f"Graph context JSON:\n{to_json(state.get('graph_context', []))}\n\n"
        "Answer the question using only this evidence. If the evidence is insufficient, say so."
    )


def message_content_to_text(content: Any) -> str:
    """Convert LLM message content to plain text.

    Args:
        content: LangChain message content.

    Returns:
        String representation of the content.
    """

    if isinstance(content, str):
        return content
    return to_json(content)


def _nested_value(document: dict[str, Any], key: str, nested_key: str) -> Any:
    """Read a nested dictionary value from a document.

    Args:
        document: Source document.
        key: Top-level dictionary key.
        nested_key: Nested dictionary key.

    Returns:
        Nested value when present, otherwise `None`.
    """

    nested = document.get(key)
    if isinstance(nested, dict):
        return nested.get(nested_key)
    return None
