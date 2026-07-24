from fastapi import FastAPI

from app.api.models import AgentRunner, AgentStreamRunner, FeedbackWriter, IngestionRunner
from app.api.routes import router
from app.logging import configure_logging
from app.metrics import instrument_prometheus
from app.settings import Settings, get_settings
from app.tracing import configure_tracing, instrument_fastapi_app


def create_app(
    agent_runner: AgentRunner | None = None,
    agent_stream_runner: AgentStreamRunner | None = None,
    feedback_repository: FeedbackWriter | None = None,
    ingestion_runner: IngestionRunner | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    if agent_runner is None:
        settings = settings or get_settings()
        configure_logging(settings.LOG_LEVEL)
        configure_tracing(settings)

    app = FastAPI(title="PaperGraph AI")
    instrument_prometheus(app)

    if settings:
        instrument_fastapi_app(app, settings)

    app.state.agent_runner = agent_runner
    app.state.agent_stream_runner = agent_stream_runner
    app.state.feedback_repository = feedback_repository
    app.state.ingestion_runner = ingestion_runner
    app.state.settings = settings or get_settings()
    app.include_router(router)
    return app


app = create_app()
