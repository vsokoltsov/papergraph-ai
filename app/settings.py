from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    OPENALEX_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o-mini"
    LOG_LEVEL: str = "INFO"
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION_NAME: str = "papers"
    QDRANT_VECTOR_SIZE: int = 384
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    POSTGRES_DATABASE_URL: str = (
        "postgresql+asyncpg://papergraph:papergraph@localhost:5432/papergraph"
    )
    POSTGRES_SYNC_DATABASE_URL: str = (
        "postgresql+psycopg://papergraph:papergraph@localhost:5432/papergraph"
    )
    API_URL: str = "http://localhost:8000"
    PROMETHEUS_PUSHGATEWAY_URL: str = "http://localhost:9091"
    OTEL_TRACING_ENABLED: bool = False
    OTEL_SERVICE_NAME: str = "papergraph-ai"
    OTEL_EXPORTER_OTLP_TRACES_ENDPOINT: str = "http://localhost:4318/v1/traces"
    LOGFIRE_ENABLED: bool = True
    LOGFIRE_TOKEN: str = ""
    LOGFIRE_API_KEY: str = ""
    INGESTION_KEYWORD: str = "graph rag"
    INGESTION_KEYWORDS: list[str] = []
    INGESTION_LIMIT: int = 10
    INGESTION_FROM_YEAR: int | None = None
    INGESTION_DLT_OUTPUT_DIR: str = ".dlt/openalex"
    INGESTION_API_TOKEN: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
