from __future__ import annotations

from typing import Any

from app.agents.research import AgentEvent, ResearchAgent, create_research_tools
from app.clients.openalex import OpenAlexClient
from app.db.neo4j import get_neo4j_driver
from app.db.qdrant import get_qdrant_client
from app.repositories.graph import GraphRepository
from app.repositories.vector import VectorRepository
from app.services.papers import PapersService
from app.settings import get_settings


class PaperGraphAgentRunner:
    """Agent runner backed by the real PaperGraph application dependencies."""

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
        )
        agent = ResearchAgent(
            tools=tools,
            model_name=settings.LLM_MODEL,
            api_key=settings.OPENAI_API_KEY,
            emit_event=events.append,
        )

        answer = await agent.run(question)
        return {"answer": answer, "events": events}
