from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from opentelemetry import trace
from qdrant_client import AsyncQdrantClient, models

from app.metrics import (
    VECTOR_PAPERS_UPLOADED_TOTAL,
    VECTOR_SEARCH_RESULTS_TOTAL,
    VECTOR_UPLOAD_DURATION_SECONDS,
    count_argument,
    count_async_results,
)

Vector = models.Document | list[float]
tracer = trace.get_tracer(__name__)


@dataclass
class VectorRepository:
    db: AsyncQdrantClient
    collection_name: str

    @VECTOR_UPLOAD_DURATION_SECONDS.time()
    @count_argument(VECTOR_PAPERS_UPLOADED_TOTAL, "ids")
    @tracer.start_as_current_span("vector.upload_papers")
    def upload_papers(
        self,
        ids: Sequence[str],
        vectors: Sequence[Vector],
        payload: Sequence[dict[str, Any]],
    ) -> None:
        self.db.upload_collection(
            collection_name=self.collection_name,
            ids=ids,
            vectors=vectors,
            payload=payload,
        )

    @count_async_results(VECTOR_SEARCH_RESULTS_TOTAL)
    @tracer.start_as_current_span("vector.search_papers")
    async def search_papers(
        self,
        query: str | list[float],
        limit: int = 5,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    ) -> list[dict[str, Any]]:
        vector_query: Vector
        if isinstance(query, str):
            vector_query = models.Document(text=query, model=model_name)
        else:
            vector_query = query

        result = await self.db.query_points(
            collection_name=self.collection_name,
            query=vector_query,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )

        return [
            {
                "id": str(point.id),
                "score": point.score,
                "payload": point.payload or {},
            }
            for point in result.points
        ]
