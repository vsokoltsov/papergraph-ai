from collections.abc import Iterator

import pytest
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams
from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import LogMessageWaitStrategy

from app.repositories.vector import VectorRepository


@pytest.fixture(scope="module")
def qdrant_url() -> Iterator[str]:
    with (
        DockerContainer("qdrant/qdrant:latest")
        .with_exposed_ports(6333)
        .waiting_for(LogMessageWaitStrategy("Actix runtime found"))
    ) as container:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(6333)
        yield f"http://{host}:{port}"


@pytest.mark.asyncio
async def test_upload_papers_stores_vectors_and_payload(qdrant_url: str) -> None:
    collection_name = "test_papers"
    client = AsyncQdrantClient(url=qdrant_url)
    await client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=4, distance=Distance.COSINE),
    )
    repository = VectorRepository(db=client, collection_name=collection_name)

    repository.upload_papers(
        ids=["00000000-0000-0000-0000-000000000001"],
        vectors=[[0.1, 0.2, 0.3, 0.4]],
        payload=[{"openalex_id": "https://openalex.org/W1", "title": "Graph RAG"}],
    )

    points = await client.retrieve(
        collection_name=collection_name,
        ids=["00000000-0000-0000-0000-000000000001"],
        with_payload=True,
        with_vectors=True,
    )

    assert len(points) == 1
    assert points[0].payload == {
        "openalex_id": "https://openalex.org/W1",
        "title": "Graph RAG",
    }
    assert isinstance(points[0].vector, list)
    assert len(points[0].vector) == 4
