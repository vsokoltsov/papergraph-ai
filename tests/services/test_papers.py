from collections.abc import Sequence
from dataclasses import dataclass, field
from uuid import NAMESPACE_URL, uuid5

import pytest

from app.clients.openalex import OpenAlexArticle
from app.services.papers import PapersService, restore_abstract


@dataclass
class FakeOpenAlexClient:
    articles: list[OpenAlexArticle]

    async def get_articles(self, query: str, limit: int = 20) -> list[OpenAlexArticle]:
        assert query == "graph rag"
        assert limit == 2
        return self.articles


@dataclass
class FakeVectorRepository:
    calls: list[dict] = field(default_factory=list)

    def upload_papers(
        self,
        ids: Sequence[str],
        vectors: Sequence,
        payload: Sequence[dict],
    ) -> None:
        self.calls.append({"ids": ids, "vectors": vectors, "payload": payload})


@dataclass
class FakeGraphRepository:
    calls: list[list[OpenAlexArticle]] = field(default_factory=list)

    async def upsert_articles_graph(self, articles) -> None:
        self.calls.append(list(articles))


def test_restore_abstract_rebuilds_text() -> None:
    assert restore_abstract({"RAG": [1], "Graph": [0]}) == "Graph RAG"


@pytest.mark.asyncio
async def test_get_articles_delegates_to_openalex_client() -> None:
    article = OpenAlexArticle(id="https://openalex.org/W1", title="Graph RAG")
    openalex_client = FakeOpenAlexClient(articles=[article])
    vector_repository = FakeVectorRepository()
    graph_repository = FakeGraphRepository()
    service = PapersService(
        openalex_client=openalex_client,
        vector_repository=vector_repository,
        graph_repository=graph_repository,
    )

    articles = await service.get_articles(query="graph rag", limit=2)

    assert articles == [article]


@pytest.mark.asyncio
async def test_insert_articles_uploads_stable_ids_vectors_payloads_and_graph() -> None:
    article = OpenAlexArticle(
        id="https://openalex.org/W1",
        doi="https://doi.org/10.123/test",
        title="Graph RAG",
        publication_year=2024,
        abstract_inverted_index={"Graph": [0], "RAG": [1]},
    )
    vector_repository = FakeVectorRepository()
    graph_repository = FakeGraphRepository()
    service = PapersService(
        openalex_client=FakeOpenAlexClient(articles=[article]),
        vector_repository=vector_repository,
        graph_repository=graph_repository,
    )

    await service.insert_articles([article])

    call = vector_repository.calls[0]
    assert call["ids"] == [str(uuid5(NAMESPACE_URL, article.id))]
    assert call["vectors"][0].text == "Graph RAG\nGraph RAG"
    assert call["payload"][0]["openalex_id"] == article.id
    assert call["payload"][0]["abstract"] == "Graph RAG"
    assert graph_repository.calls == [[article]]
