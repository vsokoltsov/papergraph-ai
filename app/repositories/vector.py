from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from qdrant_client import AsyncQdrantClient, models

Vector = models.Document | list[float]


@dataclass
class VectorRepository:
    db: AsyncQdrantClient
    collection_name: str

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
