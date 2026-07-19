import app.db.postgres as postgres
from app.db.postgres import get_postgres_engine


def test_get_postgres_engine_uses_url(monkeypatch) -> None:
    calls: list[str] = []

    def fake_create_async_engine(url: str) -> str:
        calls.append(url)
        return "engine"

    monkeypatch.setattr(postgres, "create_async_engine", fake_create_async_engine)

    assert get_postgres_engine("postgresql+asyncpg://example") == "engine"
    assert calls == ["postgresql+asyncpg://example"]
