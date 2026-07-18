from functools import lru_cache

from neo4j import AsyncDriver, AsyncGraphDatabase


@lru_cache(maxsize=1)
def get_neo4j_driver(uri: str, user: str, password: str) -> AsyncDriver:
    return AsyncGraphDatabase.driver(uri, auth=(user, password))
