"""initial_qdrant_collection

Revision ID: 20260717_0001
Revises: None
Create Date: 2026-07-17
"""

from collections.abc import Sequence

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from app.settings import get_settings

revision: str = "20260717_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
VECTOR_SIZE = 384


def upgrade() -> None:
    settings = get_settings()
    client = QdrantClient(url=settings.QDRANT_URL)

    if client.collection_exists(settings.QDRANT_COLLECTION_NAME):
        return

    client.create_collection(
        collection_name=settings.QDRANT_COLLECTION_NAME,
        vectors_config=VectorParams(
            # Must match sentence-transformers/all-MiniLM-L6-v2.
            size=VECTOR_SIZE,
            distance=Distance.COSINE,
        ),
    )


def downgrade() -> None:
    settings = get_settings()
    client = QdrantClient(url=settings.QDRANT_URL)

    if client.collection_exists(settings.QDRANT_COLLECTION_NAME):
        client.delete_collection(settings.QDRANT_COLLECTION_NAME)
