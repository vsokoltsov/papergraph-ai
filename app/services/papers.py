from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import NAMESPACE_URL, uuid5

from opentelemetry import trace
from qdrant_client import models

from app.clients.openalex import OpenAlexArticle
from app.repositories.vector import Vector

tracer = trace.get_tracer(__name__)


class OpenAlexArticlesClient(Protocol):
    async def get_articles(self, query: str, limit: int = 20) -> list[OpenAlexArticle]: ...


class PaperVectorRepository(Protocol):
    def upload_papers(
        self,
        ids: Sequence[str],
        vectors: Sequence[Vector],
        payload: Sequence[dict[str, Any]],
    ) -> None: ...


def restore_abstract(index):
    if not index:
        return None

    words = {}
    for word, positions in index.items():
        for position in positions:
            words[position] = word

    return " ".join(words[i] for i in sorted(words))


@dataclass
class PapersService:
    openalex_client: OpenAlexArticlesClient
    vector_repository: PaperVectorRepository

    @tracer.start_as_current_span("papers.get_articles")
    async def get_articles(self, query: str, limit: int = 20) -> list[OpenAlexArticle]:
        return await self.openalex_client.get_articles(query=query, limit=limit)

    @tracer.start_as_current_span("papers.insert_articles")
    def insert_articles(self, articles: list[OpenAlexArticle]) -> None:
        ids = []
        vectors = []
        payloads = []
        model_name = "sentence-transformers/all-MiniLM-L6-v2"
        for article in articles:
            abstract = restore_abstract(article.abstract_inverted_index)
            text = f"{article.title}\n{abstract or ''}"
            ids.append(str(uuid5(NAMESPACE_URL, article.id)))
            vectors.append(models.Document(text=text, model=model_name))
            payloads.append(
                {
                    "openalex_id": article.id,
                    "doi": article.doi,
                    "title": article.title,
                    "abstract": abstract,
                    "publication_year": article.publication_year,
                    "publication_date": article.publication_date,
                    "cited_by_count": article.cited_by_count,
                    "language": article.language,
                    "type": article.type,
                    "open_access": article.open_access,
                    "primary_location": article.primary_location,
                    "best_oa_location": article.best_oa_location,
                }
            )

        self.vector_repository.upload_papers(
            ids=ids,
            vectors=vectors,
            payload=payloads,
        )
