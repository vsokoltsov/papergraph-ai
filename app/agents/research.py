import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool, StructuredTool
from langchain_openai import ChatOpenAI
from opentelemetry import trace

from app.clients.openalex import OpenAlexArticle

tracer = trace.get_tracer(__name__)
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
    if event_type == "run_start":
        return f"[agent] run question={event['input']['question']!r}"
    if event_type == "run_end":
        return "[agent] final_answer_ready"
    if event_type == "tool_start":
        tool = event["tool"]
        tool_input = event["input"]
        if "query" in tool_input:
            return f"[agent] {tool} query={tool_input['query']!r} limit={tool_input['limit']}"
        if "openalex_ids" in tool_input:
            return f"[agent] {tool} papers={len(tool_input['openalex_ids'])}"
    if event_type == "tool_end":
        tool = event["tool"]
        return f"[agent] {tool} found={event['output']['count']}"

    return f"[agent] {event_type}"


def create_research_tools(
    papers_service: PapersServiceClient,
    vector_repository: PaperVectorRepository,
    graph_repository: PaperGraphRepository,
    emit_event: Callable[[AgentEvent], None] | None = None,
) -> list[BaseTool]:
    async def search_openalex(query: str, limit: int = 5) -> str:
        """Search OpenAlex for papers and return short metadata previews."""
        if emit_event:
            emit_event(
                {
                    "type": "tool_start",
                    "tool": "search_openalex",
                    "input": {"query": query, "limit": limit},
                }
            )
        articles = await papers_service.get_articles(query=query, limit=limit)
        if emit_event:
            emit_event(
                {
                    "type": "tool_end",
                    "tool": "search_openalex",
                    "output": {"count": len(articles)},
                }
            )
        return _to_json([_article_preview(article) for article in articles])

    async def ingest_papers(query: str, limit: int = 5) -> str:
        """Search OpenAlex and store matching papers in vector and graph databases."""
        if emit_event:
            emit_event(
                {
                    "type": "tool_start",
                    "tool": "ingest_papers",
                    "input": {"query": query, "limit": limit},
                }
            )
        articles = await papers_service.get_articles(query=query, limit=limit)
        await papers_service.insert_articles(articles=articles)
        if emit_event:
            emit_event(
                {
                    "type": "tool_end",
                    "tool": "ingest_papers",
                    "output": {"count": len(articles)},
                }
            )
        return _to_json(
            {
                "inserted_count": len(articles),
                "papers": [_article_preview(article) for article in articles],
            }
        )

    async def search_vector_database(query: str, limit: int = 5) -> str:
        """Search stored paper titles and abstracts in the vector database."""
        if emit_event:
            emit_event(
                {
                    "type": "tool_start",
                    "tool": "search_vector_database",
                    "input": {"query": query, "limit": limit},
                }
            )
        results = await vector_repository.search_papers(query=query, limit=limit)
        if emit_event:
            emit_event(
                {
                    "type": "tool_end",
                    "tool": "search_vector_database",
                    "output": {"count": len(results)},
                }
            )
        return _to_json(results)

    async def get_graph_context(openalex_ids: list[str]) -> str:
        """Get graph context for OpenAlex paper IDs from Neo4j."""
        if emit_event:
            emit_event(
                {
                    "type": "tool_start",
                    "tool": "get_graph_context",
                    "input": {"openalex_ids": openalex_ids},
                }
            )
        context = await graph_repository.get_paper_context(openalex_ids=openalex_ids)
        if emit_event:
            emit_event(
                {
                    "type": "tool_end",
                    "tool": "get_graph_context",
                    "output": {"count": len(context)},
                }
            )
        return _to_json(context)

    return [
        StructuredTool.from_function(coroutine=search_openalex),
        StructuredTool.from_function(coroutine=ingest_papers),
        StructuredTool.from_function(coroutine=search_vector_database),
        StructuredTool.from_function(coroutine=get_graph_context),
    ]


@dataclass
class ResearchAgent:
    tools: Sequence[BaseTool]
    model_name: str
    api_key: str
    emit_event: Callable[[AgentEvent], None] | None = None
    events: list[AgentEvent] = field(default_factory=list)

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
            system_prompt=(
                "You are PaperGraph AI, a research assistant for academic papers. "
                "Use tools to search, ingest, retrieve, and inspect graph context before "
                "answering. Prefer stored vector and graph data when available. "
                "When citing evidence, include paper titles and OpenAlex IDs. "
                "Format the final answer with these sections: Summary, Key papers, "
                "Graph insights, Evidence, and Caveats. Keep the answer concise, and "
                "state when the available data is incomplete."
            ),
        )

        result = await agent.ainvoke({"messages": [HumanMessage(content=question)]})
        messages = result["messages"]
        answer = messages[-1].content
        self._emit({"type": "run_end", "output": {"answer": answer}})
        return answer

    def _emit(self, event: AgentEvent) -> None:
        self.events.append(event)
        if self.emit_event:
            self.emit_event(event)
