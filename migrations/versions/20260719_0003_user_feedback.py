"""user_feedback

Revision ID: 20260719_0003
Revises:
Create Date: 2026-07-19
"""

from collections.abc import Sequence

from sqlalchemy import create_engine

from app.db.feedback_schema import FEEDBACK_METADATA
from app.settings import get_settings

revision: str = "20260719_0003"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("feedback",)
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _run_schema(create=True)


def downgrade() -> None:
    _run_schema(create=False)


def _run_schema(create: bool) -> None:
    settings = get_settings()
    engine = create_engine(settings.POSTGRES_SYNC_DATABASE_URL)

    try:
        with engine.begin() as connection:
            if create:
                FEEDBACK_METADATA.create_all(connection)
            else:
                FEEDBACK_METADATA.drop_all(connection)
    finally:
        engine.dispose()
