from typing import Protocol

from app.clients.openalex import OpenAlexArticle


class PaperInserter(Protocol):
    """Protocol for services that persist OpenAlex articles.

    Implementations usually write article content to multiple stores, such as
    Qdrant for vector search and Neo4j for graph relationships.
    """

    async def insert_articles(self, articles: list[OpenAlexArticle]) -> None:
        """Insert article records into downstream application stores.

        Args:
            articles: Parsed OpenAlex article models to persist.
        """
