import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool, StructuredTool
from langchain_openai import ChatOpenAI
from opentelemetry import trace

from app.clients.openalex import OpenAlexArticle

tracer = trace.get_tracer(__name__)


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


def create_research_tools(
    papers_service: PapersServiceClient,
    vector_repository: PaperVectorRepository,
    graph_repository: PaperGraphRepository,
    log: Callable[[str], None] | None = None,
) -> list[BaseTool]:
    async def search_openalex(query: str, limit: int = 5) -> str:
        """Search OpenAlex for papers and return short metadata previews."""
        if log:
            log(f"[agent] search_openalex query={query!r} limit={limit}")
        articles = await papers_service.get_articles(query=query, limit=limit)
        if log:
            log(f"[agent] search_openalex found={len(articles)}")
        return _to_json([_article_preview(article) for article in articles])

    async def ingest_papers(query: str, limit: int = 5) -> str:
        """Search OpenAlex and store matching papers in vector and graph databases."""
        if log:
            log(f"[agent] ingest_papers query={query!r} limit={limit}")
        articles = await papers_service.get_articles(query=query, limit=limit)
        await papers_service.insert_articles(articles=articles)
        if log:
            log(f"[agent] ingest_papers stored={len(articles)}")
        return _to_json(
            {
                "inserted_count": len(articles),
                "papers": [_article_preview(article) for article in articles],
            }
        )

    async def search_vector_database(query: str, limit: int = 5) -> str:
        """Search stored paper titles and abstracts in the vector database."""
        if log:
            log(f"[agent] search_vector_database query={query!r} limit={limit}")
        results = await vector_repository.search_papers(query=query, limit=limit)
        if log:
            log(f"[agent] search_vector_database found={len(results)}")
        return _to_json(results)

    async def get_graph_context(openalex_ids: list[str]) -> str:
        """Get graph context for OpenAlex paper IDs from Neo4j."""
        if log:
            log(f"[agent] get_graph_context papers={len(openalex_ids)}")
        context = await graph_repository.get_paper_context(openalex_ids=openalex_ids)
        if log:
            log(f"[agent] get_graph_context found={len(context)}")
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
    log: Callable[[str], None] | None = None

    @tracer.start_as_current_span("agent.run")
    async def run(self, question: str) -> str:
        if self.log:
            self.log(f"[agent] run question={question!r}")
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
                "When citing evidence, include paper titles and OpenAlex IDs."
            ),
        )

        result = await agent.ainvoke({"messages": [HumanMessage(content=question)]})
        messages = result["messages"]
        if self.log:
            self.log("[agent] final_answer_ready")
        return messages[-1].content
