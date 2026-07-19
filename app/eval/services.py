from __future__ import annotations

import asyncio
from collections.abc import Iterable

import httpx
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from app.db.neo4j import get_neo4j_driver
from app.eval.llm.models import AgentApproach
from app.settings import Settings


class EvaluationServiceError(RuntimeError):
    """Raised when a required evaluation service is unavailable."""


async def wait_for_llm_evaluation_services(
    settings: Settings,
    approaches: Iterable[AgentApproach],
    attempts: int = 30,
    delay: float = 1.0,
) -> None:
    """Wait for databases required by selected LLM evaluation approaches.

    Args:
        settings: Application settings with database URLs.
        approaches: Selected LLM evaluation approaches.
        attempts: Number of readiness attempts before failing.
        delay: Seconds to wait between attempts.

    Raises:
        EvaluationServiceError: If a required service stays unavailable.
    """

    selected_approaches = set(approaches)
    checks = []
    if selected_approaches & {"vector_only", "vector_plus_graph"}:
        checks.append(_wait_for_qdrant(settings.QDRANT_URL, attempts, delay))
    if selected_approaches & {"graph_only", "vector_plus_graph"}:
        checks.append(_wait_for_neo4j(settings, attempts, delay))

    if checks:
        await asyncio.gather(*checks)


async def _wait_for_qdrant(url: str, attempts: int, delay: float) -> None:
    for _ in range(attempts):
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                response = await client.get(f"{url}/collections")
            response.raise_for_status()
            return
        except (httpx.HTTPError, OSError):
            await asyncio.sleep(delay)

    raise EvaluationServiceError(
        f"Qdrant is not reachable at {url}. Start it with `docker compose up -d qdrant`."
    )


async def _wait_for_neo4j(settings: Settings, attempts: int, delay: float) -> None:
    driver = get_neo4j_driver(
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD,
    )

    for _ in range(attempts):
        try:
            await driver.verify_connectivity()
            return
        except (Neo4jError, ServiceUnavailable, OSError):
            await asyncio.sleep(delay)

    raise EvaluationServiceError(
        f"Neo4j is not reachable at {settings.NEO4J_URI}. "
        "Start it with `docker compose up -d neo4j`."
    )
