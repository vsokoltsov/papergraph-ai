from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from opentelemetry import trace
from qdrant_client import AsyncQdrantClient, models

Vector = models.Document | list[float]
tracer = trace.get_tracer(__name__)


@dataclass
class VectorRepository:
    db: AsyncQdrantClient
    collection_name: str

    @tracer.start_as_current_span("qdrant.upload_papers")
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
