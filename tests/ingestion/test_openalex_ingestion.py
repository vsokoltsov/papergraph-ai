from pathlib import Path

import pytest
from prometheus_client import REGISTRY

from app.clients.openalex import OpenAlexArticle
from app.ingestion.openalex import (
    ingest_openalex_articles,
    openalex_articles_resource,
    stage_openalex_article_records,
)
from app.ingestion.utils import build_openalex_filters, compact_openalex_records_for_dlt


def test_build_openalex_filters_includes_article_type() -> None:
    assert build_openalex_filters() == ["type:article"]


def test_build_openalex_filters_includes_from_publication_date() -> None:
    assert build_openalex_filters(from_year=2022) == [
        "type:article",
        "from_publication_date:2022-01-01",
    ]


def test_stage_openalex_article_records_writes_local_dlt_files(tmp_path: Path) -> None:
    load_info = stage_openalex_article_records(
        records=[
            {
                "id": "https://openalex.org/W1",
                "title": "Graph RAG",
                "type": "article",
            }
        ],
        output_dir=str(tmp_path),
    )

    assert "LOADED" in str(load_info)
    assert any(tmp_path.rglob("*.jsonl"))


def test_openalex_articles_resource_compacts_records() -> None:
    records = [{"id": "https://openalex.org/W1", "title": "Graph RAG"}]

    assert list(openalex_articles_resource(records)) == compact_openalex_records_for_dlt(records)


def test_compact_openalex_records_for_dlt_keeps_payload_as_text() -> None:
    compact_records = compact_openalex_records_for_dlt(
        [
            {
                "id": "https://openalex.org/W1",
                "title": "Graph RAG",
                "abstract_inverted_index": {"Graph": [0]},
                "best_oa_location": None,
            }
        ]
    )

    assert compact_records == [
        {
            "id": "https://openalex.org/W1",
            "doi": None,
            "title": "Graph RAG",
            "publication_year": None,
            "publication_date": None,
            "type": None,
            "raw_payload": (
                '{"abstract_inverted_index": {"Graph": [0]}, '
                '"best_oa_location": null, "id": "https://openalex.org/W1", '
                '"title": "Graph RAG"}'
            ),
        }
    ]


@pytest.mark.asyncio
async def test_ingest_openalex_articles_stages_and_inserts(monkeypatch, tmp_path: Path) -> None:
    records = [
        {
            "id": "https://openalex.org/W1",
            "title": "Graph RAG",
            "type": "article",
        }
    ]
    service = FakePaperInserter()

    monkeypatch.setattr(
        "app.ingestion.openalex.fetch_openalex_article_records",
        lambda **kwargs: records,
    )
    monkeypatch.setattr(
        "app.ingestion.openalex.stage_openalex_article_records",
        lambda **kwargs: "loaded",
    )

    result = await ingest_openalex_articles(
        service=service,
        query="graph rag",
        limit=1,
        api_key="openalex-key",
        dlt_output_dir=str(tmp_path),
        from_year=2020,
    )

    assert result.staged_records == 1
    assert result.inserted_articles == 1
    assert result.dlt_load_info == "loaded"
    assert service.articles == [OpenAlexArticle.model_validate(records[0])]
    assert get_counter_value("papergraph_openalex_articles_total") >= 1
    assert get_counter_value("papergraph_dlt_records_staged_total") >= 1
    assert get_counter_value("papergraph_ingestion_runs_total", {"status": "success"}) >= 1


class FakePaperInserter:
    def __init__(self) -> None:
        self.articles: list[OpenAlexArticle] = []

    async def insert_articles(self, articles: list[OpenAlexArticle]) -> None:
        self.articles = articles


def get_counter_value(name: str, labels: dict[str, str] | None = None) -> float:
    metric = REGISTRY.get_sample_value(name, labels or {})
    assert metric is not None
    return metric
