import pytest

from app.clients.openalex import OpenAlexClient


class FakeResponse:
    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return {
            "results": [
                {
                    "id": "https://openalex.org/W1",
                    "doi": "https://doi.org/10.123/test",
                    "title": "Graph RAG for Science",
                    "publication_year": 2024,
                    "best_oa_location": {"pdf_url": "https://example.com/paper.pdf"},
                    "abstract_inverted_index": {"Graph": [0], "RAG": [1]},
                }
            ]
        }


class FakeAsyncClient:
    def __init__(self, timeout: int) -> None:
        self.timeout = timeout

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        pass

    async def get(self, url: str, params: dict) -> FakeResponse:
        assert url == "https://api.openalex.org/works"
        assert params["api_key"] == "test-key"
        assert params["search"] == "graph rag"
        assert params["filter"] == "type:article"
        assert params["per-page"] == 5
        return FakeResponse()


@pytest.mark.asyncio
async def test_get_articles_returns_pydantic_models(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.clients.openalex.httpx.AsyncClient", FakeAsyncClient)

    client = OpenAlexClient(api_key="test-key")
    articles = await client.get_articles(query="graph rag", limit=5)

    assert len(articles) == 1
    assert articles[0].id == "https://openalex.org/W1"
    assert articles[0].title == "Graph RAG for Science"
    assert articles[0].best_oa_location == {"pdf_url": "https://example.com/paper.pdf"}
