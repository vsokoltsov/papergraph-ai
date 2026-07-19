"""user_feedback

Revision ID: 20260719_0003
Revises: 20260717_0002
Create Date: 2026-07-19
"""

from collections.abc import Sequence

from sqlalchemy import create_engine, text

from app.settings import get_settings

revision: str = "20260719_0003"
down_revision: str | Sequence[str] | None = "20260717_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE_QUERIES: Sequence[str] = [
    """
    CREATE TABLE IF NOT EXISTS agent_runs (
        run_id TEXT PRIMARY KEY,
        question TEXT NOT NULL,
        answer TEXT NOT NULL,
        approach TEXT,
        prompt_tokens INTEGER,
        completion_tokens INTEGER,
        total_tokens INTEGER,
        duration_seconds DOUBLE PRECISION,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS feedback (
        id BIGSERIAL PRIMARY KEY,
        run_id TEXT NOT NULL REFERENCES agent_runs(run_id) ON DELETE CASCADE,
        rating TEXT NOT NULL CHECK (rating IN ('thumbs_up', 'thumbs_down')),
        comment TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS feedback_created_at ON feedback (created_at)",
    "CREATE INDEX IF NOT EXISTS feedback_rating ON feedback (rating)",
    "CREATE INDEX IF NOT EXISTS feedback_run_id ON feedback (run_id)",
    "CREATE INDEX IF NOT EXISTS agent_runs_created_at ON agent_runs (created_at)",
    "CREATE INDEX IF NOT EXISTS agent_runs_approach ON agent_runs (approach)",
]

DOWNGRADE_QUERIES: Sequence[str] = [
    "DROP INDEX IF EXISTS agent_runs_approach",
    "DROP INDEX IF EXISTS agent_runs_created_at",
    "DROP INDEX IF EXISTS feedback_run_id",
    "DROP INDEX IF EXISTS feedback_rating",
    "DROP INDEX IF EXISTS feedback_created_at",
    "DROP TABLE IF EXISTS feedback",
    "DROP TABLE IF EXISTS agent_runs",
]


def upgrade() -> None:
    _run_queries(UPGRADE_QUERIES)


def downgrade() -> None:
    _run_queries(DOWNGRADE_QUERIES)


def _run_queries(queries: Sequence[str]) -> None:
    settings = get_settings()
    engine = create_engine(settings.POSTGRES_SYNC_DATABASE_URL)

    try:
        with engine.begin() as connection:
            for query in queries:
                connection.execute(text(query))
    finally:
        engine.dispose()
