"""initial_neo4j_schema

Revision ID: 20260717_0002
Revises: 20260717_0001
Create Date: 2026-07-17
"""

from collections.abc import Sequence
from typing import LiteralString

from neo4j import GraphDatabase

from app.settings import get_settings

revision: str = "20260717_0002"
down_revision: str | Sequence[str] | None = "20260717_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE_QUERIES: Sequence[LiteralString] = [
    """
    CREATE CONSTRAINT paper_openalex_id IF NOT EXISTS
    FOR (p:Paper)
    REQUIRE p.openalex_id IS UNIQUE
    """,
    """
    CREATE CONSTRAINT author_openalex_id IF NOT EXISTS
    FOR (a:Author)
    REQUIRE a.openalex_id IS UNIQUE
    """,
    """
    CREATE CONSTRAINT institution_openalex_id IF NOT EXISTS
    FOR (i:Institution)
    REQUIRE i.openalex_id IS UNIQUE
    """,
    """
    CREATE CONSTRAINT source_openalex_id IF NOT EXISTS
    FOR (s:Source)
    REQUIRE s.openalex_id IS UNIQUE
    """,
    """
    CREATE CONSTRAINT topic_openalex_id IF NOT EXISTS
    FOR (t:Topic)
    REQUIRE t.openalex_id IS UNIQUE
    """,
    """
    CREATE INDEX paper_doi IF NOT EXISTS
    FOR (p:Paper)
    ON (p.doi)
    """,
    """
    CREATE INDEX paper_publication_year IF NOT EXISTS
    FOR (p:Paper)
    ON (p.publication_year)
    """,
    """
    CREATE INDEX paper_title IF NOT EXISTS
    FOR (p:Paper)
    ON (p.title)
    """,
    """
    CREATE INDEX author_display_name IF NOT EXISTS
    FOR (a:Author)
    ON (a.display_name)
    """,
    """
    CREATE INDEX institution_display_name IF NOT EXISTS
    FOR (i:Institution)
    ON (i.display_name)
    """,
    """
    CREATE INDEX topic_display_name IF NOT EXISTS
    FOR (t:Topic)
    ON (t.display_name)
    """,
]


DOWNGRADE_QUERIES: Sequence[LiteralString] = [
    "DROP INDEX topic_display_name IF EXISTS",
    "DROP INDEX institution_display_name IF EXISTS",
    "DROP INDEX author_display_name IF EXISTS",
    "DROP INDEX paper_title IF EXISTS",
    "DROP INDEX paper_publication_year IF EXISTS",
    "DROP INDEX paper_doi IF EXISTS",
    "DROP CONSTRAINT topic_openalex_id IF EXISTS",
    "DROP CONSTRAINT source_openalex_id IF EXISTS",
    "DROP CONSTRAINT institution_openalex_id IF EXISTS",
    "DROP CONSTRAINT author_openalex_id IF EXISTS",
    "DROP CONSTRAINT paper_openalex_id IF EXISTS",
]


def upgrade() -> None:
    _run_queries(UPGRADE_QUERIES)


def downgrade() -> None:
    _run_queries(DOWNGRADE_QUERIES)


def _run_queries(queries: Sequence[LiteralString]) -> None:
    settings = get_settings()
    driver = GraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
    )

    try:
        with driver.session() as session:
            for query in queries:
                session.run(query).consume()
    finally:
        driver.close()
