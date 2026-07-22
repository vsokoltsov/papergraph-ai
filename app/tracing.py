import contextlib

import logfire
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.settings import Settings

_logfire_configured = False
_logfire_httpx_instrumented = False
_logfire_openai_instrumented = False
_logfire_pydantic_instrumented = False


def configure_tracing(settings: Settings) -> None:
    if settings.LOGFIRE_ENABLED:
        configure_logfire(settings)
        return

    if not settings.OTEL_TRACING_ENABLED:
        return

    resource = Resource.create({"service.name": settings.OTEL_SERVICE_NAME})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_TRACES_ENDPOINT)
    provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)


def configure_logfire(settings: Settings) -> None:
    global _logfire_configured
    global _logfire_httpx_instrumented
    global _logfire_openai_instrumented
    global _logfire_pydantic_instrumented

    if _logfire_configured:
        return

    additional_span_processors = []
    if settings.OTEL_TRACING_ENABLED:
        exporter = OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_TRACES_ENDPOINT)
        additional_span_processors.append(BatchSpanProcessor(exporter))

    token = settings.LOGFIRE_TOKEN or settings.LOGFIRE_API_KEY or None
    logfire.configure(
        token=token,
        service_name=settings.OTEL_SERVICE_NAME,
        send_to_logfire=True if token else "if-token-present",
        console=False,
        metrics=False,
        additional_span_processors=additional_span_processors,
    )
    _logfire_configured = True

    if not _logfire_httpx_instrumented:
        with contextlib.suppress(Exception):
            logfire.instrument_httpx()
        _logfire_httpx_instrumented = True

    if not _logfire_openai_instrumented:
        with contextlib.suppress(Exception):
            logfire.instrument_openai()
        _logfire_openai_instrumented = True

    if not _logfire_pydantic_instrumented:
        logfire.instrument_pydantic(record="failure")
        _logfire_pydantic_instrumented = True


def instrument_fastapi_app(app, settings: Settings) -> None:
    if settings.LOGFIRE_ENABLED:
        logfire.instrument_fastapi(app)
        return

    if not settings.OTEL_TRACING_ENABLED:
        return

    FastAPIInstrumentor.instrument_app(app)
