from __future__ import annotations

from typing import Any

from app.ingestion.dlthub import trigger_openalex_ingestion_api
from app.settings import Settings


def test_trigger_openalex_ingestion_api_posts_configured_payload(monkeypatch) -> None:
    calls: list[dict[str, Any]] = []

    monkeypatch.setattr("app.ingestion.dlthub.httpx.Client", lambda timeout: FakeClient(calls))

    result = trigger_openalex_ingestion_api(
        Settings(
            API_URL="https://papergraph.example.com",
            INGESTION_KEYWORD="mathematics graph theory",
            INGESTION_LIMIT=7,
            INGESTION_FROM_YEAR=2021,
            INGESTION_DLT_OUTPUT_DIR=".dlt/dlthub-openalex",
            INGESTION_API_TOKEN="token",
        )
    )

    assert result == {"staged_records": 7}
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
        }
    ]


class FakeResponse:
    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict[str, int]:
        return {"staged_records": 7}


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
