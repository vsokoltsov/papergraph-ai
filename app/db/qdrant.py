from functools import lru_cache
from qdrant_client import AsyncQdrantClient

@lru_cache(maxsize=1)
def get_qdrant_client(url: str) -> AsyncQdrantClient:
    return AsyncQdrantClient(url=url)
