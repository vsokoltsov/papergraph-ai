from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from functools import wraps
from inspect import signature
from typing import Any, cast

import tiktoken
from fastapi import FastAPI, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from prometheus_client.exposition import push_to_gateway
from starlette.middleware.base import BaseHTTPMiddleware

HTTP_REQUESTS_TOTAL = Counter(
    "papergraph_http_requests_total",
    "Total HTTP requests handled by the API.",
    ["method", "path", "status"],
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "papergraph_http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ["method", "path"],
)
KNOWN_HTTP_ROUTES = (
    ("GET", "/health", "200"),
    ("POST", "/agent/runs", "200"),
    ("POST", "/agent/runs/stream", "200"),
    ("POST", "/feedback", "200"),
    ("POST", "/feedback", "422"),
)
AGENT_RUNS_TOTAL = Counter(
    "papergraph_agent_runs_total",
    "Total agent runs.",
    ["status"],
)
AGENT_RUN_DURATION_SECONDS = Histogram(
    "papergraph_agent_run_duration_seconds",
    "Agent run duration in seconds.",
)
AGENT_RUN_TOKENS = Histogram(
    "papergraph_agent_run_tokens",
    "Estimated tokens per agent run.",
    ["token_type"],
    buckets=(50, 100, 250, 500, 1000, 2000, 4000, 8000, 16000, 32000),
)
AGENT_TOKENS_TOTAL = Counter(
    "papergraph_agent_tokens_total",
    "Estimated total tokens used by agent runs.",
    ["token_type"],
)
AGENT_TOOL_CALLS_TOTAL = Counter(
    "papergraph_agent_tool_calls_total",
    "Total agent tool calls.",
    ["tool"],
)
AGENT_TOOL_DURATION_SECONDS = Histogram(
    "papergraph_agent_tool_duration_seconds",
    "Agent tool call duration in seconds.",
    ["tool"],
)
AGENT_TOOL_RESULTS_TOTAL = Counter(
    "papergraph_agent_tool_results_total",
    "Total result items returned by agent tools.",
    ["tool"],
)
OPENALEX_ARTICLES_TOTAL = Counter(
    "papergraph_openalex_articles_total",
    "Total OpenAlex articles returned.",
)
INGESTION_RUNS_TOTAL = Counter(
    "papergraph_ingestion_runs_total",
    "Total ingestion runs.",
    ["status"],
)
INGESTION_RUN_DURATION_SECONDS = Histogram(
    "papergraph_ingestion_run_duration_seconds",
    "Ingestion run duration in seconds.",
)
DLT_RECORDS_STAGED_TOTAL = Counter(
    "papergraph_dlt_records_staged_total",
    "Total records staged with dlt.",
)
VECTOR_PAPERS_UPLOADED_TOTAL = Counter(
    "papergraph_vector_papers_uploaded_total",
    "Total papers uploaded to the vector database.",
)
VECTOR_UPLOAD_DURATION_SECONDS = Histogram(
    "papergraph_vector_upload_duration_seconds",
    "Vector paper upload duration in seconds.",
)
VECTOR_SEARCH_RESULTS_TOTAL = Counter(
    "papergraph_vector_search_results_total",
    "Total vector search results returned.",
)
GRAPH_PAPERS_UPSERTED_TOTAL = Counter(
    "papergraph_graph_papers_upserted_total",
    "Total papers upserted into the graph database.",
)
GRAPH_SEARCH_RESULTS_TOTAL = Counter(
    "papergraph_graph_search_results_total",
    "Total graph search results returned.",
)
GRAPH_CONTEXT_RESULTS_TOTAL = Counter(
    "papergraph_graph_context_results_total",
    "Total graph context rows returned.",
)
LLM_EVAL_ANSWER_GOOD_RATE = Gauge(
    "papergraph_llm_eval_answer_good_rate",
    "Share of LLM evaluation answers judged as good.",
    ["approach"],
)
LLM_EVAL_TRAJECTORY_GOOD_RATE = Gauge(
    "papergraph_llm_eval_trajectory_good_rate",
    "Share of LLM evaluation tool trajectories judged as good.",
    ["approach"],
)
LLM_EVAL_EXAMPLES_TOTAL = Gauge(
    "papergraph_llm_eval_examples_total",
    "Total LLM evaluation examples judged.",
    ["approach"],
)
FEEDBACK_TOTAL = Counter(
    "papergraph_feedback_total",
    "Total user feedback records submitted.",
    ["rating"],
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Collect Prometheus HTTP request metrics for the FastAPI app."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        path = request.url.path
        if path == "/metrics":
            return await call_next(request)

        start = time.monotonic()
        response = await call_next(request)
        duration = time.monotonic() - start
        HTTP_REQUESTS_TOTAL.labels(
            method=request.method,
            path=path,
            status=str(response.status_code),
        ).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(method=request.method, path=path).observe(duration)
        return response


def instrument_prometheus(app: FastAPI) -> None:
    """Expose Prometheus metrics and install request instrumentation."""

    initialize_http_metrics()
    app.add_middleware(PrometheusMiddleware)

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def initialize_http_metrics() -> None:
    """Create zero-valued HTTP metric series for known API routes."""

    for method, path, status in KNOWN_HTTP_ROUTES:
        HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status=status).inc(0)


def track_agent_run[F: Callable[..., Any]](func: F) -> F:
    """Track duration and success/error counts for an async agent run."""

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.monotonic()
        try:
            result = await func(*args, **kwargs)
            AGENT_RUNS_TOTAL.labels(status="success").inc()
            return result
        except Exception:
            AGENT_RUNS_TOTAL.labels(status="error").inc()
            raise
        finally:
            AGENT_RUN_DURATION_SECONDS.observe(time.monotonic() - start)

    return cast(F, wrapper)


def track_agent_tool[F: Callable[..., Any]](
    tool: str,
) -> Callable[[F], F]:
    """Track duration and call count for an async agent tool."""

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.monotonic()
            AGENT_TOOL_CALLS_TOTAL.labels(tool=tool).inc()
            try:
                return await func(*args, **kwargs)
            finally:
                AGENT_TOOL_DURATION_SECONDS.labels(tool=tool).observe(time.monotonic() - start)

        return cast(F, wrapper)

    return decorator


def count_async_results[F: Callable[..., Any]](
    metric: Counter,
) -> Callable[[F], F]:
    """Increment a counter by the number of items returned from an async function."""

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = await func(*args, **kwargs)
            metric.inc(len(result))
            return result

        return cast(F, wrapper)

    return decorator


def count_async_argument[F: Callable[..., Any]](
    metric: Counter,
    argument_name: str,
) -> Callable[[F], F]:
    """Increment a counter by the size of an argument after async function success."""

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = await func(*args, **kwargs)
            bound = signature(func).bind(*args, **kwargs)
            bound.apply_defaults()
            metric.inc(len(bound.arguments[argument_name]))
            return result

        return cast(F, wrapper)

    return decorator


def count_argument[F: Callable[..., Any]](metric: Counter, argument_name: str) -> Callable[[F], F]:
    """Increment a counter by the size of an argument after sync function success."""

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = func(*args, **kwargs)
            bound = signature(func).bind(*args, **kwargs)
            bound.apply_defaults()
            metric.inc(len(bound.arguments[argument_name]))
            return result

        return cast(F, wrapper)

    return decorator


def record_agent_tool_results(tool: str, count: int) -> None:
    """Record how many result items an agent tool returned."""

    AGENT_TOOL_RESULTS_TOTAL.labels(tool=tool).inc(count)


def record_llm_evaluation_summary(summary: list[dict[str, Any]]) -> None:
    """Record LLM evaluation summary rows as Prometheus gauges."""

    for row in summary:
        approach = str(row["approach"])
        LLM_EVAL_ANSWER_GOOD_RATE.labels(approach=approach).set(row["answer_good_rate"])
        LLM_EVAL_TRAJECTORY_GOOD_RATE.labels(approach=approach).set(row["trajectory_good_rate"])
        LLM_EVAL_EXAMPLES_TOTAL.labels(approach=approach).set(row["total"])


def push_metrics_to_gateway(gateway_url: str, job: str) -> None:
    """Push current process metrics for short-lived CLI jobs."""

    push_to_gateway(gateway_url, job=job, registry=REGISTRY)


def estimate_tokens(value: Any, model_name: str) -> int:
    """Estimate token count for arbitrary text-like data."""

    text = stringify_for_tokens(value)
    if not text:
        return 0

    try:
        encoding = tiktoken.encoding_for_model(model_name)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")

    return len(encoding.encode(text))


def stringify_for_tokens(value: Any) -> str:
    """Convert LangChain message content or plain values into text."""

    match value:
        case None:
            return ""
        case str():
            return value
        case list():
            return " ".join(stringify_for_tokens(item) for item in value)
        case dict():
            return " ".join(stringify_for_tokens(item) for item in value.values())
        case _:
            return str(value)
