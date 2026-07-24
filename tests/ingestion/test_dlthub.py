from __future__ import annotations

from typing import Any

from app.ingestion.dlthub import (
    build_ingestion_payload,
    ingestion_keywords,
    trigger_openalex_ingestion_api,
)
from app.settings import Settings


def test_trigger_openalex_ingestion_api_posts_configured_payloads(monkeypatch) -> None:
    calls: list[dict[str, Any]] = []

    monkeypatch.setattr("app.ingestion.dlthub.httpx.Client", lambda timeout: FakeClient(calls))

    result = trigger_openalex_ingestion_api(
        Settings(
            API_URL="https://papergraph.example.com",
            INGESTION_KEYWORDS=["mathematics graph theory", "topology"],
            INGESTION_LIMIT=7,
            INGESTION_FROM_YEAR=2021,
            INGESTION_DLT_OUTPUT_DIR=".dlt/dlthub-openalex",
            INGESTION_API_TOKEN="token",
        )
    )

    assert result == {
        "keyword_count": 2,
        "staged_records": 14,
        "inserted_articles": 10,
        "results": [
            {"staged_records": 7, "inserted_articles": 5},
            {"staged_records": 7, "inserted_articles": 5},
        ],
    }
    assert calls == [
        {
            "url": "https://papergraph.example.com/ingestions/openalex",
            "json": {
                "keyword": "mathematics graph theory",
                "limit": 7,
                "from_year": 2021,
                "dlt_output_dir": ".dlt/dlthub-openalex",
            },
            "headers": {"Authorization": "Bearer token"},
        },
        {
            "url": "https://papergraph.example.com/ingestions/openalex",
            "json": {
                "keyword": "topology",
                "limit": 7,
                "from_year": 2021,
                "dlt_output_dir": ".dlt/dlthub-openalex",
            },
            "headers": {"Authorization": "Bearer token"},
        },
    ]


def test_ingestion_keywords_uses_list_before_single_keyword() -> None:
    assert ingestion_keywords(
        Settings(
            INGESTION_KEYWORD="graph rag",
            INGESTION_KEYWORDS=[" mathematics ", "", "topology"],
        )
    ) == ["mathematics", "topology"]


def test_ingestion_keywords_falls_back_to_single_keyword() -> None:
    assert ingestion_keywords(Settings(INGESTION_KEYWORD=" graph rag ")) == ["graph rag"]


def test_build_ingestion_payload_omits_missing_from_year() -> None:
    assert build_ingestion_payload(Settings(INGESTION_FROM_YEAR=None), "graph rag") == {
        "keyword": "graph rag",
        "limit": 10,
        "dlt_output_dir": ".dlt/openalex",
    }


class FakeResponse:
    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict[str, int]:
        return {"staged_records": 7, "inserted_articles": 5}


class FakeClient:
    def __init__(self, calls: list[dict[str, Any]]) -> None:
        self.calls = calls

    def __enter__(self) -> FakeClient:
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def post(self, url: str, json: dict[str, Any], headers: dict[str, str]) -> FakeResponse:
        self.calls.append({"url": url, "json": json, "headers": headers})
        return FakeResponse()
