from dataclasses import dataclass
from typing import Any, List

import httpx
from pydantic import BaseModel, ConfigDict


class OpenAlexArticle(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    doi: str | None = None
    title: str | None = None
    display_name: str | None = None
    relevance_score: float | None = None
    publication_year: int | None = None
    publication_date: str | None = None
    ids: dict[str, Any] | None = None
    language: str | None = None
    primary_location: dict[str, Any] | None = None
    type: str | None = None
    indexed_in: list[str] | None = None
    open_access: dict[str, Any] | None = None
    authorships: list[dict[str, Any]] | None = None
    institutions: list[dict[str, Any]] | None = None
    has_fulltext: bool | None = None
    cited_by_count: int | None = None
    primary_topic: dict[str, Any] | None = None
    topics: list[dict[str, Any]] | None = None
    keywords: list[dict[str, Any]] | None = None
    has_content: dict[str, Any] | None = None
    content_urls: dict[str, Any] | None = None
    referenced_works_count: int | None = None
    referenced_works: list[str] | None = None
    related_works: list[str] | None = None
    abstract_inverted_index: dict[str, list[int]] | None = None
    updated_date: str | None = None
    created_date: str | None = None


@dataclass
class OpenAlexClient:
    api_key: str


    def get_articles(self, query: str, limit: int = 20) -> List[OpenAlexArticle]:
        filters = ["type:article"]
        response = httpx.get(
            "https://api.openalex.org/works",
            params={
                "api_key": self.api_key,
                "search": query,
                "filter": ",".join(filters),
                "per-page": limit,
            },
            timeout=20,
        )
        response.raise_for_status()

        data = response.json()
        articles = data["results"]
        return [OpenAlexArticle.model_validate(article) for article in articles]
