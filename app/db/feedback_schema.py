from sqlalchemy import (
    CheckConstraint,
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import BIGINT, TIMESTAMP

FEEDBACK_METADATA = MetaData()

agent_runs_table = Table(
    "agent_runs",
    FEEDBACK_METADATA,
    Column("run_id", String, primary_key=True),
    Column("question", Text, nullable=False),
    Column("answer", Text, nullable=False),
    Column("approach", String),
    Column("prompt_tokens", Integer),
    Column("completion_tokens", Integer),
    Column("total_tokens", Integer),
    Column("duration_seconds", Float),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=func.now()),
    Index("agent_runs_created_at", "created_at"),
    Index("agent_runs_approach", "approach"),
)

feedback_table = Table(
    "feedback",
    FEEDBACK_METADATA,
    Column("id", BIGINT, primary_key=True, autoincrement=True),
    Column(
        "run_id",
        String,
        ForeignKey("agent_runs.run_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("rating", String, nullable=False),
    Column("comment", Text),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("rating IN ('thumbs_up', 'thumbs_down')", name="feedback_rating_check"),
    Index("feedback_created_at", "created_at"),
    Index("feedback_rating", "rating"),
    Index("feedback_run_id", "run_id"),
)
