from __future__ import annotations

from typing import Any

from app.agents.research import AgentEvent, ResearchAgent, create_research_tools
from app.clients.openalex import OpenAlexClient
from app.db.neo4j import get_neo4j_driver
from app.db.qdrant import get_qdrant_client
from app.eval.llm.models import AgentApproach
from app.repositories.graph import GraphRepository
from app.repositories.vector import VectorRepository
from app.services.papers import PapersService
from app.settings import get_settings


class PaperGraphAgentRunner:
    """Agent runner backed by the real PaperGraph application dependencies."""

    def __init__(self, approach: AgentApproach) -> None:
        self.approach = approach

    async def run(self, question: str) -> dict[str, Any]:
        """Run the PaperGraph research agent.

        Args:
            question: User question to send to the agent.

        Returns:
            Dictionary with final answer and emitted agent events.
        """

        settings = get_settings()
        events: list[AgentEvent] = []
        openalex_client = OpenAlexClient(api_key=settings.OPENALEX_API_KEY)
        qdrant_db = get_qdrant_client(url=settings.QDRANT_URL)
        neo4j_db = get_neo4j_driver(
            uri=settings.NEO4J_URI,
            user=settings.NEO4J_USER,
            password=settings.NEO4J_PASSWORD,
        )
        vector_repository = VectorRepository(
            db=qdrant_db,
            collection_name=settings.QDRANT_COLLECTION_NAME,
        )
        graph_repository = GraphRepository(db=neo4j_db)
        papers_service = PapersService(
            openalex_client=openalex_client,
            vector_repository=vector_repository,
            graph_repository=graph_repository,
        )
        tools = create_research_tools(
            papers_service=papers_service,
            vector_repository=vector_repository,
            graph_repository=graph_repository,
            emit_event=events.append,
            enabled_tools=enabled_tools_for_approach(self.approach),
        )
        agent = ResearchAgent(
            tools=tools,
            model_name=settings.LLM_MODEL,
            api_key=settings.OPENAI_API_KEY,
            emit_event=events.append,
            system_prompt=system_prompt_for_approach(self.approach),
        )

        answer = await agent.run(question)
        return {"answer": answer, "events": events}


def enabled_tools_for_approach(approach: AgentApproach) -> set[str]:
    """Return tool names enabled for an evaluation approach.

    Args:
        approach: Agent approach to evaluate.

    Returns:
        Tool names available to the agent.
    """

    match approach:
        case "vector_only":
            return {"search_vector_database"}
        case "graph_only":
            return {"search_graph_database", "get_graph_context"}
        case "vector_plus_graph":
            return {"search_vector_database", "get_graph_context"}


def system_prompt_for_approach(approach: AgentApproach) -> str:
    """Return the system prompt for one evaluation approach.

    Args:
        approach: Agent approach to evaluate.

    Returns:
        Approach-specific agent system prompt.
    """

    shared = (
        "You are PaperGraph AI, a research assistant for academic papers. "
        "Answer using only tool results. Qdrant stores semantic paper content from titles "
        "and abstracts. Neo4j stores graph metadata and relationships such as authors, "
        "institutions, topics, sources, and citations. When citing evidence, include paper "
        "titles and OpenAlex IDs. Format the final answer with these sections: Summary, "
        "Key papers, Graph insights, Evidence, and Caveats. Keep the answer concise, and "
        "state when the available data is incomplete."
    )

    match approach:
        case "vector_only":
            return f"{shared} Use vector database search only. Do not request graph context."
        case "graph_only":
            return (
                f"{shared} Use graph database search and graph context only. Do not use vector "
                "search. Because Neo4j does not store abstracts, be explicit when the graph "
                "metadata is insufficient for content-level claims."
            )
        case "vector_plus_graph":
            return (
                f"{shared} Always use vector search first to find relevant papers by title and "
                "abstract. Then inspect graph context for the returned OpenAlex IDs before "
                "answering, especially for comparisons, topics, sources, authors, institutions, "
                "and citation relationships."
            )
