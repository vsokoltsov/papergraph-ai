from typing import Dict, Any
from dataclasses import dataclass
from qdrant_client import AsyncQdrantClient
from qdrant_client import models

@dataclass
class VectorRepository:
    db: AsyncQdrantClient
    collection_name: str

    def upload_papers(
        self,
        ids: list[str],
        vectors: list[models.Document],
        payload: list[Dict[str, Any]]
    ) -> None:
        self.db.upload_collection(
            collection_name=self.collection_name,
            ids=ids,
            vectors=vectors,
            payload=payload,
        )
    
