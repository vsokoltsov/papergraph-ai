"""Run the PaperGraph AI research agent.

Usage:
    python -m app.agent "Find papers about graph rag"
"""

from __future__ import annotations

import argparse
import asyncio

from app.agents.research import ResearchAgent, create_research_tools
from app.clients.openalex import OpenAlexClient
from app.db.neo4j import get_neo4j_driver
from app.db.qdrant import get_qdrant_client
from app.repositories.graph import GraphRepository
from app.repositories.vector import VectorRepository
from app.services.papers import PapersService
from app.settings import get_settings
from app.tracing import configure_tracing


async def main() -> None:
    settings = get_settings()
    configure_tracing(settings)

    parser = argparse.ArgumentParser(description="Run the PaperGraph AI research agent.")
    parser.add_argument("question", help="Research question or goal.")
    args = parser.parse_args()

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
        log=print,
    )
    agent = ResearchAgent(
        tools=tools,
        model_name=settings.LLM_MODEL,
        api_key=settings.OPENAI_API_KEY,
        log=print,
    )

    answer = await agent.run(args.question)
    print()
    print("Answer:")
    print(answer)


if __name__ == "__main__":
    asyncio.run(main())
