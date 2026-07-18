from dataclasses import dataclass
from typing import LiteralString

from neo4j import AsyncDriver, AsyncManagedTransaction
from opentelemetry import trace

tracer = trace.get_tracer(__name__)


@dataclass
class GraphRepository:
    db: AsyncDriver

    @tracer.start_as_current_span("graph.upsert_paper")
    async def upsert_paper(self, article) -> None:
        async with self.db.session() as session:
            await session.run(
                """
                MERGE (p:Paper {openalex_id: $openalex_id})
                SET p.doi = $doi,
                    p.title = $title,
                    p.publication_year = $publication_year,
                    p.publication_date = $publication_date,
                    p.language = $language,
                    p.type = $type,
                    p.cited_by_count = $cited_by_count
                """,
                openalex_id=article.id,
                doi=article.doi,
                title=article.title,
                publication_year=article.publication_year,
                publication_date=article.publication_date,
                language=article.language,
                type=article.type,
                cited_by_count=article.cited_by_count,
            )

    @tracer.start_as_current_span("graph.upsert_authors")
    async def upsert_authors(self, article) -> None:
        rows = []
        for authorship in article.authorships or []:
            author = authorship.get("author") or {}
            author_id = author.get("id")
            if not author_id:
                continue

            rows.append(
                {
                    "author_id": author_id,
                    "display_name": author.get("display_name"),
                    "orcid": author.get("orcid"),
                    "paper_id": article.id,
                    "author_position": authorship.get("author_position"),
                    "is_corresponding": authorship.get("is_corresponding"),
                }
            )

        if not rows:
            return

        async with self.db.session() as session:
            await session.run(
                """
                UNWIND $rows AS row

                MERGE (a:Author {openalex_id: row.author_id})
                SET a.display_name = row.display_name,
                    a.orcid = row.orcid

                MERGE (p:Paper {openalex_id: row.paper_id})

                MERGE (a)-[r:WROTE]->(p)
                SET r.author_position = row.author_position,
                    r.is_corresponding = row.is_corresponding
                """,
                rows=rows,
            )

    @tracer.start_as_current_span("graph.upsert_institutions")
    async def upsert_institutions(self, article) -> None:
        rows = []
        for authorship in article.authorships or []:
            author = authorship.get("author") or {}
            author_id = author.get("id")
            if not author_id:
                continue

            for institution in authorship.get("institutions") or []:
                institution_id = institution.get("id")
                if not institution_id:
                    continue

                rows.append(
                    {
                        "author_id": author_id,
                        "institution_id": institution_id,
                        "display_name": institution.get("display_name"),
                        "ror": institution.get("ror"),
                        "country_code": institution.get("country_code"),
                        "type": institution.get("type"),
                        "paper_id": article.id,
                    }
                )

        if not rows:
            return

        async with self.db.session() as session:
            await session.run(
                """
                UNWIND $rows AS row

                MERGE (a:Author {openalex_id: row.author_id})
                MERGE (i:Institution {openalex_id: row.institution_id})
                SET i.display_name = row.display_name,
                    i.ror = row.ror,
                    i.country_code = row.country_code,
                    i.type = row.type

                MERGE (p:Paper {openalex_id: row.paper_id})

                MERGE (a)-[:AFFILIATED_WITH]->(i)
                MERGE (i)-[:CONTRIBUTED_TO]->(p)
                """,
                rows=rows,
            )

    @tracer.start_as_current_span("graph.upsert_source")
    async def upsert_source(self, article) -> None:
        source = (article.primary_location or {}).get("source")
        if not source or not source.get("id"):
            return

        async with self.db.session() as session:
            await session.run(
                """
                MERGE (p:Paper {openalex_id: $paper_id})

                MERGE (s:Source {openalex_id: $source_id})
                SET s.display_name = $display_name,
                    s.type = $type,
                    s.issn_l = $issn_l,
                    s.host_organization = $host_organization

                MERGE (p)-[:PUBLISHED_IN]->(s)
                """,
                paper_id=article.id,
                source_id=source.get("id"),
                display_name=source.get("display_name"),
                type=source.get("type"),
                issn_l=source.get("issn_l"),
                host_organization=source.get("host_organization"),
            )

    @tracer.start_as_current_span("graph.upsert_topics")
    async def upsert_topics(self, article) -> None:
        rows = []
        for topic in article.topics or []:
            topic_id = topic.get("id")
            if not topic_id:
                continue

            rows.append(
                {
                    "paper_id": article.id,
                    "topic_id": topic_id,
                    "display_name": topic.get("display_name"),
                    "score": topic.get("score"),
                }
            )

        if not rows:
            return

        async with self.db.session() as session:
            await session.run(
                """
                UNWIND $rows AS row

                MERGE (p:Paper {openalex_id: row.paper_id})

                MERGE (t:Topic {openalex_id: row.topic_id})
                SET t.display_name = row.display_name

                MERGE (p)-[r:HAS_TOPIC]->(t)
                SET r.score = row.score
                """,
                rows=rows,
            )

    @tracer.start_as_current_span("graph.upsert_primary_topic")
    async def upsert_primary_topic(self, article) -> None:
        topic = article.primary_topic
        if not topic or not topic.get("id"):
            return

        async with self.db.session() as session:
            await session.run(
                """
                MERGE (p:Paper {openalex_id: $paper_id})

                MERGE (t:Topic {openalex_id: $topic_id})
                SET t.display_name = $display_name

                MERGE (p)-[:PRIMARY_TOPIC]->(t)
                """,
                paper_id=article.id,
                topic_id=topic.get("id"),
                display_name=topic.get("display_name"),
            )

    @tracer.start_as_current_span("graph.upsert_references")
    async def upsert_references(self, article) -> None:
        rows = [
            {"paper_id": article.id, "referenced_work_id": referenced_work_id}
            for referenced_work_id in article.referenced_works or []
            if referenced_work_id
        ]

        if not rows:
            return

        async with self.db.session() as session:
            await session.run(
                """
                UNWIND $rows AS row

                MERGE (p:Paper {openalex_id: row.paper_id})
                MERGE (ref:Paper {openalex_id: row.referenced_work_id})
                MERGE (p)-[:CITES]->(ref)
                """,
                rows=rows,
            )

    @tracer.start_as_current_span("graph.upsert_article_graph")
    async def upsert_article_graph(self, article) -> None:
        await self.upsert_paper(article)
        await self.upsert_authors(article)
        await self.upsert_institutions(article)
        await self.upsert_source(article)
        await self.upsert_topics(article)
        await self.upsert_primary_topic(article)
        await self.upsert_references(article)

    @tracer.start_as_current_span("graph.upsert_articles_graph")
    async def upsert_articles_graph(self, articles) -> None:
        articles = list(articles)
        if not articles:
            return

        paper_rows = [
            {
                "openalex_id": article.id,
                "doi": article.doi,
                "title": article.title,
                "publication_year": article.publication_year,
                "publication_date": article.publication_date,
                "language": article.language,
                "type": article.type,
                "cited_by_count": article.cited_by_count,
            }
            for article in articles
            if article.id
        ]
        author_rows = []
        institution_rows = []
        source_rows = []
        topic_rows = []
        primary_topic_rows = []
        reference_rows = []

        for article in articles:
            for authorship in article.authorships or []:
                author = authorship.get("author") or {}
                author_id = author.get("id")
                if not author_id:
                    continue

                author_rows.append(
                    {
                        "author_id": author_id,
                        "display_name": author.get("display_name"),
                        "orcid": author.get("orcid"),
                        "paper_id": article.id,
                        "author_position": authorship.get("author_position"),
                        "is_corresponding": authorship.get("is_corresponding"),
                    }
                )

                for institution in authorship.get("institutions") or []:
                    institution_id = institution.get("id")
                    if not institution_id:
                        continue

                    institution_rows.append(
                        {
                            "author_id": author_id,
                            "institution_id": institution_id,
                            "display_name": institution.get("display_name"),
                            "ror": institution.get("ror"),
                            "country_code": institution.get("country_code"),
                            "type": institution.get("type"),
                            "paper_id": article.id,
                        }
                    )

            source = (article.primary_location or {}).get("source")
            if source and source.get("id"):
                source_rows.append(
                    {
                        "paper_id": article.id,
                        "source_id": source.get("id"),
                        "display_name": source.get("display_name"),
                        "type": source.get("type"),
                        "issn_l": source.get("issn_l"),
                        "host_organization": source.get("host_organization"),
                    }
                )

            for topic in article.topics or []:
                topic_id = topic.get("id")
                if not topic_id:
                    continue

                topic_rows.append(
                    {
                        "paper_id": article.id,
                        "topic_id": topic_id,
                        "display_name": topic.get("display_name"),
                        "score": topic.get("score"),
                    }
                )

            primary_topic = article.primary_topic
            if primary_topic and primary_topic.get("id"):
                primary_topic_rows.append(
                    {
                        "paper_id": article.id,
                        "topic_id": primary_topic.get("id"),
                        "display_name": primary_topic.get("display_name"),
                    }
                )

            reference_rows.extend(
                {
                    "paper_id": article.id,
                    "referenced_work_id": referenced_work_id,
                }
                for referenced_work_id in article.referenced_works or []
                if referenced_work_id
            )

        await self._run_bulk(
            """
            UNWIND $rows AS row

            MERGE (p:Paper {openalex_id: row.openalex_id})
            SET p.doi = row.doi,
                p.title = row.title,
                p.publication_year = row.publication_year,
                p.publication_date = row.publication_date,
                p.language = row.language,
                p.type = row.type,
                p.cited_by_count = row.cited_by_count
            """,
            paper_rows,
        )

        await self._run_bulk(
            """
            UNWIND $rows AS row

            MERGE (a:Author {openalex_id: row.author_id})
            SET a.display_name = row.display_name,
                a.orcid = row.orcid

            MERGE (p:Paper {openalex_id: row.paper_id})

            MERGE (a)-[r:WROTE]->(p)
            SET r.author_position = row.author_position,
                r.is_corresponding = row.is_corresponding
            """,
            author_rows,
        )
        await self._run_bulk(
            """
            UNWIND $rows AS row

            MERGE (a:Author {openalex_id: row.author_id})
            MERGE (i:Institution {openalex_id: row.institution_id})
            SET i.display_name = row.display_name,
                i.ror = row.ror,
                i.country_code = row.country_code,
                i.type = row.type

            MERGE (p:Paper {openalex_id: row.paper_id})

            MERGE (a)-[:AFFILIATED_WITH]->(i)
            MERGE (i)-[:CONTRIBUTED_TO]->(p)
            """,
            institution_rows,
        )
        await self._run_bulk(
            """
            UNWIND $rows AS row

            MERGE (p:Paper {openalex_id: row.paper_id})

            MERGE (s:Source {openalex_id: row.source_id})
            SET s.display_name = row.display_name,
                s.type = row.type,
                s.issn_l = row.issn_l,
                s.host_organization = row.host_organization

            MERGE (p)-[:PUBLISHED_IN]->(s)
            """,
            source_rows,
        )
        await self._run_bulk(
            """
            UNWIND $rows AS row

            MERGE (p:Paper {openalex_id: row.paper_id})

            MERGE (t:Topic {openalex_id: row.topic_id})
            SET t.display_name = row.display_name

            MERGE (p)-[r:HAS_TOPIC]->(t)
            SET r.score = row.score
            """,
            topic_rows,
        )
        await self._run_bulk(
            """
            UNWIND $rows AS row

            MERGE (p:Paper {openalex_id: row.paper_id})

            MERGE (t:Topic {openalex_id: row.topic_id})
            SET t.display_name = row.display_name

            MERGE (p)-[:PRIMARY_TOPIC]->(t)
            """,
            primary_topic_rows,
        )
        await self._run_bulk(
            """
            UNWIND $rows AS row

            MERGE (p:Paper {openalex_id: row.paper_id})
            MERGE (ref:Paper {openalex_id: row.referenced_work_id})
            MERGE (p)-[:CITES]->(ref)
            """,
            reference_rows,
        )

    @tracer.start_as_current_span("graph.get_paper_context")
    async def get_paper_context(self, openalex_ids: list[str]) -> list[dict]:
        if not openalex_ids:
            return []

        async with self.db.session() as session:
            result = await session.run(
                """
                MATCH (p:Paper)
                WHERE p.openalex_id IN $openalex_ids
                RETURN
                    p {
                        .openalex_id,
                        .doi,
                        .title,
                        .publication_year,
                        .publication_date,
                        .language,
                        .type,
                        .cited_by_count
                    } AS paper,
                    [
                        (a:Author)-[w:WROTE]->(p) |
                        a {
                            .openalex_id,
                            .display_name,
                            .orcid,
                            author_position: w.author_position,
                            is_corresponding: w.is_corresponding
                        }
                    ] AS authors,
                    [
                        (i:Institution)-[:CONTRIBUTED_TO]->(p) |
                        i {
                            .openalex_id,
                            .display_name,
                            .ror,
                            .country_code,
                            .type
                        }
                    ] AS institutions,
                    [
                        (p)-[:PUBLISHED_IN]->(s:Source) |
                        s {
                            .openalex_id,
                            .display_name,
                            .type,
                            .issn_l,
                            .host_organization
                        }
                    ] AS sources,
                    [
                        (p)-[r:HAS_TOPIC]->(t:Topic) |
                        t {
                            .openalex_id,
                            .display_name,
                            score: r.score
                        }
                    ] AS topics,
                    [
                        (p)-[:PRIMARY_TOPIC]->(primary_topic:Topic) |
                        primary_topic {
                            .openalex_id,
                            .display_name
                        }
                    ] AS primary_topics,
                    [
                        (p)-[:CITES]->(referenced_paper:Paper) |
                        referenced_paper {
                            .openalex_id,
                            .doi,
                            .title,
                            .publication_year
                        }
                    ] AS references
                """,
                openalex_ids=openalex_ids,
            )
            return await result.data()

    @tracer.start_as_current_span("graph.search_papers")
    async def search_papers(self, query: str, limit: int = 5) -> list[dict]:
        async with self.db.session() as session:
            result = await session.run(
                """
                WITH toLower($search_query) AS search_query
                MATCH (p:Paper)
                OPTIONAL MATCH (p)-[:HAS_TOPIC|PRIMARY_TOPIC]->(t:Topic)
                OPTIONAL MATCH (p)-[:PUBLISHED_IN]->(s:Source)
                WITH p, collect(DISTINCT t.display_name) AS topics,
                     collect(DISTINCT s.display_name) AS sources, search_query
                WHERE toLower(coalesce(p.title, "")) CONTAINS search_query
                   OR any(topic IN topics WHERE toLower(coalesce(topic, "")) CONTAINS search_query)
                   OR any(
                       source IN sources
                       WHERE toLower(coalesce(source, "")) CONTAINS search_query
                   )
                RETURN
                    p {
                        .openalex_id,
                        .doi,
                        .title,
                        .publication_year,
                        .publication_date,
                        .language,
                        .type,
                        .cited_by_count
                    } AS paper,
                    topics,
                    sources
                ORDER BY coalesce(p.cited_by_count, 0) DESC
                LIMIT $limit
                """,
                search_query=query.lower(),
                limit=limit,
            )
            return await result.data()

    @tracer.start_as_current_span("graph.run_bulk")
    async def _run_bulk(self, query: LiteralString, rows: list[dict]) -> None:
        if not rows:
            return

        async with self.db.session() as session:
            await session.execute_write(self._execute_bulk, query, rows)

    @staticmethod
    async def _execute_bulk(
        tx: AsyncManagedTransaction,
        query: LiteralString,
        rows: list[dict],
    ) -> None:
        result = await tx.run(query, rows=rows)
        await result.consume()
