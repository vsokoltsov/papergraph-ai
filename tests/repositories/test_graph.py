from collections.abc import Iterator

import pytest
from neo4j import AsyncGraphDatabase
from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import LogMessageWaitStrategy

from app.clients.openalex import OpenAlexArticle
from app.repositories.graph import GraphRepository, search_query_tokens


@pytest.fixture(scope="module")
def neo4j_uri() -> Iterator[str]:
    with (
        DockerContainer("neo4j:5-community")
        .with_env("NEO4J_AUTH", "neo4j/testpassword")
        .with_exposed_ports(7687)
        .waiting_for(LogMessageWaitStrategy("Started."))
    ) as container:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(7687)
        yield f"bolt://{host}:{port}"


@pytest.mark.asyncio
async def test_upsert_articles_graph_stores_nodes_relationships_and_is_idempotent(
    neo4j_uri: str,
) -> None:
    driver = AsyncGraphDatabase.driver(
        neo4j_uri,
        auth=("neo4j", "testpassword"),
    )
    repository = GraphRepository(db=driver)
    article = OpenAlexArticle(
        id="https://openalex.org/W1",
        doi="https://doi.org/10.123/test",
        title="Graph RAG",
        publication_year=2024,
        publication_date="2024-01-01",
        language="en",
        type="article",
        cited_by_count=7,
        authorships=[
            {
                "author": {
                    "id": "https://openalex.org/A1",
                    "display_name": "Ada Lovelace",
                    "orcid": "https://orcid.org/0000-0001",
                },
                "author_position": "first",
                "is_corresponding": True,
                "institutions": [
                    {
                        "id": "https://openalex.org/I1",
                        "display_name": "Graph University",
                        "ror": "https://ror.org/123",
                        "country_code": "US",
                        "type": "education",
                    }
                ],
            }
        ],
        primary_location={
            "source": {
                "id": "https://openalex.org/S1",
                "display_name": "Journal of Graphs",
                "type": "journal",
                "issn_l": "1234-5678",
                "host_organization": "https://openalex.org/P1",
            }
        },
        topics=[
            {
                "id": "https://openalex.org/T1",
                "display_name": "Retrieval Augmented Generation",
                "score": 0.95,
            }
        ],
        primary_topic={
            "id": "https://openalex.org/T1",
            "display_name": "Retrieval Augmented Generation",
        },
        referenced_works=["https://openalex.org/W2"],
    )

    await repository.upsert_articles_graph([article])
    await repository.upsert_articles_graph([article])
    contexts = await repository.get_paper_context([article.id])
    graph_results = await repository.search_papers("graph", limit=1)

    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (p:Paper {openalex_id: $paper_id})
            RETURN
                p.title AS title,
                p.doi AS doi,
                p.publication_year AS publication_year,
                p.cited_by_count AS cited_by_count,
                count { MATCH (:Author)-[:WROTE]->(p) } AS authors,
                count {
                    MATCH (:Author)-[:AFFILIATED_WITH]->(:Institution)
                        -[:CONTRIBUTED_TO]->(p)
                } AS institutions,
                count { MATCH (p)-[:PUBLISHED_IN]->(:Source) } AS sources,
                count { MATCH (p)-[:HAS_TOPIC]->(:Topic) } AS topics,
                count { MATCH (p)-[:PRIMARY_TOPIC]->(:Topic) } AS primary_topics,
                count { MATCH (p)-[:CITES]->(:Paper) } AS references
            """,
            paper_id=article.id,
        )
        row = await result.single(strict=True)

    await driver.close()

    assert row["title"] == "Graph RAG"
    assert row["doi"] == "https://doi.org/10.123/test"
    assert row["publication_year"] == 2024
    assert row["cited_by_count"] == 7
    assert row["authors"] == 1
    assert row["institutions"] == 1
    assert row["sources"] == 1
    assert row["topics"] == 1
    assert row["primary_topics"] == 1
    assert row["references"] == 1
    assert contexts == [
        {
            "paper": {
                "openalex_id": "https://openalex.org/W1",
                "doi": "https://doi.org/10.123/test",
                "title": "Graph RAG",
                "publication_year": 2024,
                "publication_date": "2024-01-01",
                "language": "en",
                "type": "article",
                "cited_by_count": 7,
            },
            "authors": [
                {
                    "openalex_id": "https://openalex.org/A1",
                    "display_name": "Ada Lovelace",
                    "orcid": "https://orcid.org/0000-0001",
                    "author_position": "first",
                    "is_corresponding": True,
                }
            ],
            "institutions": [
                {
                    "openalex_id": "https://openalex.org/I1",
                    "display_name": "Graph University",
                    "ror": "https://ror.org/123",
                    "country_code": "US",
                    "type": "education",
                }
            ],
            "sources": [
                {
                    "openalex_id": "https://openalex.org/S1",
                    "display_name": "Journal of Graphs",
                    "type": "journal",
                    "issn_l": "1234-5678",
                    "host_organization": "https://openalex.org/P1",
                }
            ],
            "topics": [
                {
                    "openalex_id": "https://openalex.org/T1",
                    "display_name": "Retrieval Augmented Generation",
                    "score": 0.95,
                }
            ],
            "primary_topics": [
                {
                    "openalex_id": "https://openalex.org/T1",
                    "display_name": "Retrieval Augmented Generation",
                }
            ],
            "references": [
                {
                    "openalex_id": "https://openalex.org/W2",
                    "doi": None,
                    "title": None,
                    "publication_year": None,
                }
            ],
        }
    ]
    assert graph_results == [
        {
            "paper": {
                "openalex_id": "https://openalex.org/W1",
                "doi": "https://doi.org/10.123/test",
                "title": "Graph RAG",
                "publication_year": 2024,
                "publication_date": "2024-01-01",
                "language": "en",
                "type": "article",
                "cited_by_count": 7,
            },
            "score": 1,
            "topics": ["Retrieval Augmented Generation"],
            "sources": ["Journal of Graphs"],
        }
    ]


def test_search_query_tokens_normalizes_simple_query_text() -> None:
    assert search_query_tokens("KG-RAG_graph for LLM") == ["rag", "graph", "for", "llm"]
