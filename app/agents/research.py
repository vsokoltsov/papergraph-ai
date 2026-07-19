import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

import structlog
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool, StructuredTool
from langchain_openai import ChatOpenAI
from opentelemetry import trace

from app.clients.openalex import OpenAlexArticle
from app.metrics import (
    AGENT_RUN_TOKENS,
    AGENT_TOKENS_TOTAL,
    estimate_tokens,
    record_agent_tool_results,
    track_agent_run,
    track_agent_tool,
)

tracer = trace.get_tracer(__name__)
logger = structlog.get_logger(__name__)
AgentEvent = dict[str, Any]


class PapersServiceClient(Protocol):
    async def get_articles(self, query: str, limit: int = 20) -> list[OpenAlexArticle]: ...

    async def insert_articles(self, articles: list[OpenAlexArticle]) -> None: ...


class PaperVectorRepository(Protocol):
    async def search_papers(
        self,
        query: str | list[float],
        limit: int = 5,
    ) -> list[dict[str, Any]]: ...


class PaperGraphRepository(Protocol):
    async def search_papers(self, query: str, limit: int = 5) -> list[dict]: ...

    async def get_paper_context(self, openalex_ids: list[str]) -> list[dict]: ...


def _to_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


def _article_preview(article: OpenAlexArticle) -> dict[str, Any]:
    return {
        "openalex_id": article.id,
        "doi": article.doi,
        "title": article.title,
        "publication_year": article.publication_year,
        "cited_by_count": article.cited_by_count,
    }


def format_agent_event(event: AgentEvent) -> str:
    event_type = event["type"]
    match event_type:
        case "run_start":
            return f"[agent] run question={event['input']['question']!r}"
        case "run_end":
            return "[agent] final_answer_ready"
        case "tool_start":
            tool = event["tool"]
            tool_input = event["input"]
            match tool_input:
                case {"query": query, "limit": limit}:
                    return f"[agent] {tool} query={query!r} limit={limit}"
                case {"openalex_ids": openalex_ids}:
                    return f"[agent] {tool} papers={len(openalex_ids)}"
        case "tool_end":
            tool = event["tool"]
            return f"[agent] {tool} found={event['output']['count']}"

    return f"[agent] {event_type}"


def log_agent_event(event: AgentEvent) -> None:
    event_type = event["type"]
    log_data: dict[str, Any] = {"event_type": event_type}

    if "tool" in event:
        log_data["tool"] = event["tool"]
    match event_type:
        case "run_start":
            log_data["question"] = event["input"]["question"]
        case "run_end":
            log_data["answer_length"] = len(event["output"]["answer"])
        case "tool_start":
            log_data.update(event["input"])
        case "tool_end":
            log_data.update(event["output"])

    logger.info("agent_event", **log_data)


def create_research_tools(
    papers_service: PapersServiceClient,
    vector_repository: PaperVectorRepository,
    graph_repository: PaperGraphRepository,
    emit_event: Callable[[AgentEvent], None] | None = None,
    enabled_tools: set[str] | None = None,
) -> list[BaseTool]:
    def is_enabled(tool_name: str) -> bool:
        return enabled_tools is None or tool_name in enabled_tools

    @track_agent_tool("search_openalex")
    async def search_openalex(query: str, limit: int = 5) -> str:
        """Search OpenAlex for papers and return short metadata previews."""
        _emit_tool_event(
            emit_event,
            {
                "type": "tool_start",
                "tool": "search_openalex",
                "input": {"query": query, "limit": limit},
            },
        )
        articles = await papers_service.get_articles(query=query, limit=limit)
        record_agent_tool_results("search_openalex", len(articles))
        _emit_tool_event(
            emit_event,
            {
                "type": "tool_end",
                "tool": "search_openalex",
                "output": {"count": len(articles)},
            },
        )
        return _to_json([_article_preview(article) for article in articles])

    @track_agent_tool("ingest_papers")
    async def ingest_papers(query: str, limit: int = 5) -> str:
        """Search OpenAlex and store matching papers in vector and graph databases."""
        _emit_tool_event(
            emit_event,
            {
                "type": "tool_start",
                "tool": "ingest_papers",
                "input": {"query": query, "limit": limit},
            },
        )
        articles = await papers_service.get_articles(query=query, limit=limit)
        await papers_service.insert_articles(articles=articles)
        record_agent_tool_results("ingest_papers", len(articles))
        _emit_tool_event(
            emit_event,
            {
                "type": "tool_end",
                "tool": "ingest_papers",
                "output": {"count": len(articles)},
            },
        )
        return _to_json(
            {
                "inserted_count": len(articles),
                "papers": [_article_preview(article) for article in articles],
            }
        )

    @track_agent_tool("search_vector_database")
    async def search_vector_database(query: str, limit: int = 5) -> str:
        """Search stored paper titles and abstracts in the vector database."""
        _emit_tool_event(
            emit_event,
            {
                "type": "tool_start",
                "tool": "search_vector_database",
                "input": {"query": query, "limit": limit},
            },
        )
        results = await vector_repository.search_papers(query=query, limit=limit)
        record_agent_tool_results("search_vector_database", len(results))
        _emit_tool_event(
            emit_event,
            {
                "type": "tool_end",
                "tool": "search_vector_database",
                "output": {"count": len(results)},
            },
        )
        return _to_json(results)

    @track_agent_tool("search_graph_database")
    async def search_graph_database(query: str, limit: int = 5) -> str:
        """Search stored paper metadata, topics, and sources in the graph database."""
        _emit_tool_event(
            emit_event,
            {
                "type": "tool_start",
                "tool": "search_graph_database",
                "input": {"query": query, "limit": limit},
            },
        )
        results = await graph_repository.search_papers(query=query, limit=limit)
        record_agent_tool_results("search_graph_database", len(results))
        _emit_tool_event(
            emit_event,
            {
                "type": "tool_end",
                "tool": "search_graph_database",
                "output": {"count": len(results)},
            },
        )
        return _to_json(results)

    @track_agent_tool("get_graph_context")
    async def get_graph_context(openalex_ids: list[str]) -> str:
        """Get graph context for OpenAlex paper IDs from Neo4j."""
        _emit_tool_event(
            emit_event,
            {
                "type": "tool_start",
                "tool": "get_graph_context",
                "input": {"openalex_ids": openalex_ids},
            },
        )
        context = await graph_repository.get_paper_context(openalex_ids=openalex_ids)
        record_agent_tool_results("get_graph_context", len(context))
        _emit_tool_event(
            emit_event,
            {
                "type": "tool_end",
                "tool": "get_graph_context",
                "output": {"count": len(context)},
            },
        )
        return _to_json(context)

    tools = {
        "search_openalex": StructuredTool.from_function(coroutine=search_openalex),
        "ingest_papers": StructuredTool.from_function(coroutine=ingest_papers),
        "search_vector_database": StructuredTool.from_function(coroutine=search_vector_database),
        "search_graph_database": StructuredTool.from_function(coroutine=search_graph_database),
        "get_graph_context": StructuredTool.from_function(coroutine=get_graph_context),
    }

    return [tool for tool_name, tool in tools.items() if is_enabled(tool_name)]


@dataclass
class ResearchAgent:
    tools: Sequence[BaseTool]
    model_name: str
    api_key: str
    emit_event: Callable[[AgentEvent], None] | None = None
    system_prompt: str | None = None
    events: list[AgentEvent] = field(default_factory=list)

    @track_agent_run
    @tracer.start_as_current_span("agent.run")
    async def run(self, question: str) -> str:
        self._emit({"type": "run_start", "input": {"question": question}})
        llm = ChatOpenAI(
            model=self.model_name,
            api_key=self.api_key,
            temperature=0,
        )
        agent = create_agent(
            model=llm,
            tools=self.tools,
            system_prompt=self.system_prompt
            or (
                "You are PaperGraph AI, a research assistant for academic papers. "
                "Use vector database search first to retrieve relevant papers by title "
                "and abstract. Then inspect graph context for the returned OpenAlex IDs "
                "to add authors, institutions, topics, sources, and citation relationships. "
                "Use graph search only when the user asks for graph metadata or when vector "
                "results need relationship context. "
                "When citing evidence, include paper titles and OpenAlex IDs. "
                "Format the final answer with these sections: Summary, Key papers, "
                "Graph insights, Evidence, and Caveats. Keep the answer concise, and "
                "state when the available data is incomplete."
            ),
        )

        result = await agent.ainvoke({"messages": [HumanMessage(content=question)]})
        messages = result["messages"]
        answer = messages[-1].content
        record_agent_tokens(
            messages=messages,
            question=question,
            answer=answer,
            model_name=self.model_name,
        )
        self._emit({"type": "run_end", "output": {"answer": answer}})
        return answer

    def _emit(self, event: AgentEvent) -> None:
        self.events.append(event)
        log_agent_event(event)
        if self.emit_event:
            self.emit_event(event)


def _emit_tool_event(
    emit_event: Callable[[AgentEvent], None] | None,
    event: AgentEvent,
) -> None:
    log_agent_event(event)
    if emit_event:
        emit_event(event)


def record_agent_tokens(
    messages: list[Any],
    question: str,
    answer: Any,
    model_name: str,
) -> None:
    prompt_text = [question]
    for message in messages[:-1]:
        prompt_text.append(getattr(message, "content", ""))

    prompt_tokens = estimate_tokens(prompt_text, model_name)
    completion_tokens = estimate_tokens(answer, model_name)
    total_tokens = prompt_tokens + completion_tokens

    for token_type, value in {
        "prompt": prompt_tokens,
        "completion": completion_tokens,
        "total": total_tokens,
    }.items():
        AGENT_RUN_TOKENS.labels(token_type=token_type).observe(value)
        AGENT_TOKENS_TOTAL.labels(token_type=token_type).inc(value)
