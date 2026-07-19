from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from grafanalib.core import Dashboard, GridPos, Target, Time, TimeSeries

GRAFANA_DASHBOARD = cast(Any, Dashboard)
GRAFANA_GRID_POS = cast(Any, GridPos)
GRAFANA_TARGET = cast(Any, Target)
GRAFANA_TIME = cast(Any, Time)
GRAFANA_TIME_SERIES = cast(Any, TimeSeries)

PROMETHEUS = {"type": "prometheus", "uid": "Prometheus"}
DEFAULT_TIME_RANGE = GRAFANA_TIME("now-5m", "now")
SCHEMA_VERSION = 39


@dataclass(frozen=True)
class DashboardFile:
    name: str
    dashboard: Any


def dashboard(
    uid: str,
    title: str,
    tags: list[str],
    panels: list[Any],
) -> Any:
    return GRAFANA_DASHBOARD(
        title=title,
        uid=uid,
        tags=tags,
        timezone="browser",
        schemaVersion=SCHEMA_VERSION,
        version=1,
        refresh="10s",
        time=DEFAULT_TIME_RANGE,
        panels=panels,
    )


def panel(
    panel_id: int,
    title: str,
    expr: str,
    legend: str,
    grid: Any,
    unit: str = "",
    value_min: int | None = None,
    value_max: int | None = None,
) -> Any:
    return GRAFANA_TIME_SERIES(
        id=panel_id,
        title=title,
        dataSource=PROMETHEUS,
        gridPos=grid,
        targets=[GRAFANA_TARGET(expr=expr, legendFormat=legend)],
        unit=unit,
        valueMin=value_min,
        valueMax=value_max,
    )


DASHBOARDS = [
    DashboardFile(
        name="papergraph-overview.json",
        dashboard=dashboard(
            uid="papergraph-overview",
            title="PaperGraph Overview",
            tags=["papergraph", "overview"],
            panels=[
                panel(
                    1,
                    "HTTP Requests / sec",
                    "sum(rate(papergraph_http_requests_total[5m])) by (path)",
                    "{{path}}",
                    GRAFANA_GRID_POS(h=8, w=12, x=0, y=0),
                ),
                panel(
                    2,
                    "HTTP p95 Latency",
                    "histogram_quantile(0.95, "
                    "sum(rate(papergraph_http_request_duration_seconds_bucket[5m])) "
                    "by (le, path))",
                    "{{path}}",
                    GRAFANA_GRID_POS(h=8, w=12, x=12, y=0),
                    unit="s",
                ),
                panel(
                    3,
                    "Agent Runs",
                    "sum(papergraph_agent_runs_total) by (status)",
                    "{{status}}",
                    GRAFANA_GRID_POS(h=8, w=8, x=0, y=8),
                ),
                panel(
                    4,
                    "Tokens",
                    "sum(papergraph_agent_tokens_total) by (token_type)",
                    "{{token_type}}",
                    GRAFANA_GRID_POS(h=8, w=8, x=8, y=8),
                ),
                panel(
                    5,
                    "HTTP Error Rate",
                    'sum(rate(papergraph_http_requests_total{status=~"5..|4.."}[5m])) by (status)',
                    "{{status}}",
                    GRAFANA_GRID_POS(h=8, w=8, x=16, y=8),
                ),
            ],
        ),
    ),
    DashboardFile(
        name="papergraph-llm-tokens.json",
        dashboard=dashboard(
            uid="papergraph-llm-tokens",
            title="PaperGraph LLM and Token Usage",
            tags=["papergraph", "llm", "tokens"],
            panels=[
                panel(
                    1,
                    "Average Tokens per Agent Run",
                    "sum(papergraph_agent_run_tokens_sum) by (token_type) / "
                    "sum(papergraph_agent_run_tokens_count) by (token_type)",
                    "{{token_type}}",
                    GRAFANA_GRID_POS(h=8, w=12, x=0, y=0),
                ),
                panel(
                    2,
                    "p95 Tokens per Agent Run",
                    "histogram_quantile(0.95, "
                    "sum(papergraph_agent_run_tokens_bucket) by (le, token_type))",
                    "{{token_type}}",
                    GRAFANA_GRID_POS(h=8, w=12, x=12, y=0),
                ),
                panel(
                    3,
                    "Cumulative Tokens",
                    "sum(papergraph_agent_tokens_total) by (token_type)",
                    "{{token_type}}",
                    GRAFANA_GRID_POS(h=6, w=8, x=0, y=8),
                ),
                panel(
                    4,
                    "Agent Run p95 Duration",
                    "histogram_quantile(0.95, "
                    "sum(papergraph_agent_run_duration_seconds_bucket) by (le))",
                    "p95",
                    GRAFANA_GRID_POS(h=6, w=8, x=8, y=8),
                    unit="s",
                ),
                panel(
                    5,
                    "Agent Run Success vs Error",
                    "sum(papergraph_agent_runs_total) by (status)",
                    "{{status}}",
                    GRAFANA_GRID_POS(h=6, w=8, x=16, y=8),
                ),
                panel(
                    6,
                    "LLM Eval Answer Good Rate",
                    "papergraph_llm_eval_answer_good_rate",
                    "{{approach}}",
                    GRAFANA_GRID_POS(h=6, w=8, x=0, y=14),
                    unit="percentunit",
                    value_min=0,
                    value_max=1,
                ),
                panel(
                    7,
                    "LLM Eval Trajectory Good Rate",
                    "papergraph_llm_eval_trajectory_good_rate",
                    "{{approach}}",
                    GRAFANA_GRID_POS(h=6, w=8, x=8, y=14),
                    unit="percentunit",
                    value_min=0,
                    value_max=1,
                ),
                panel(
                    8,
                    "LLM Eval Examples",
                    "papergraph_llm_eval_examples_total",
                    "{{approach}}",
                    GRAFANA_GRID_POS(h=6, w=8, x=16, y=14),
                ),
            ],
        ),
    ),
    DashboardFile(
        name="papergraph-agent-tools.json",
        dashboard=dashboard(
            uid="papergraph-agent-tools",
            title="PaperGraph Agent Tools",
            tags=["papergraph", "agent", "tools"],
            panels=[
                panel(
                    1,
                    "Tool Calls",
                    "sum(papergraph_agent_tool_calls_total) by (tool)",
                    "{{tool}}",
                    GRAFANA_GRID_POS(h=8, w=12, x=0, y=0),
                ),
                panel(
                    2,
                    "Tool p95 Duration",
                    "histogram_quantile(0.95, "
                    "sum(papergraph_agent_tool_duration_seconds_bucket) by (le, tool))",
                    "{{tool}}",
                    GRAFANA_GRID_POS(h=8, w=12, x=12, y=0),
                    unit="s",
                ),
                panel(
                    3,
                    "Tool Results",
                    "sum(papergraph_agent_tool_results_total) by (tool)",
                    "{{tool}}",
                    GRAFANA_GRID_POS(h=8, w=12, x=0, y=8),
                ),
                panel(
                    4,
                    "Average Results per Tool Call",
                    "sum(papergraph_agent_tool_results_total) by (tool) / "
                    "sum(papergraph_agent_tool_calls_total) by (tool)",
                    "{{tool}}",
                    GRAFANA_GRID_POS(h=8, w=12, x=12, y=8),
                ),
            ],
        ),
    ),
    DashboardFile(
        name="papergraph-retrieval-databases.json",
        dashboard=dashboard(
            uid="papergraph-retrieval-databases",
            title="PaperGraph Retrieval Databases",
            tags=["papergraph", "retrieval", "databases"],
            panels=[
                panel(
                    1,
                    "Vector Search Results",
                    "sum(papergraph_vector_search_results_total)",
                    "qdrant",
                    GRAFANA_GRID_POS(h=8, w=8, x=0, y=0),
                ),
                panel(
                    2,
                    "Graph Search Results",
                    "sum(papergraph_graph_search_results_total)",
                    "neo4j search",
                    GRAFANA_GRID_POS(h=8, w=8, x=8, y=0),
                ),
                panel(
                    3,
                    "Graph Context Rows",
                    "sum(papergraph_graph_context_results_total)",
                    "neo4j context",
                    GRAFANA_GRID_POS(h=8, w=8, x=16, y=0),
                ),
                panel(
                    4,
                    "Retrieval Tool Calls",
                    "sum(papergraph_agent_tool_calls_total{tool=~"
                    '"search_vector_database|search_graph_database|get_graph_context"}) '
                    "by (tool)",
                    "{{tool}}",
                    GRAFANA_GRID_POS(h=8, w=12, x=0, y=8),
                ),
                panel(
                    5,
                    "Retrieval Tool Latency p95",
                    "histogram_quantile(0.95, sum(papergraph_agent_tool_duration_seconds_bucket{"
                    'tool=~"search_vector_database|search_graph_database|get_graph_context"}) '
                    "by (le, tool))",
                    "{{tool}}",
                    GRAFANA_GRID_POS(h=8, w=12, x=12, y=8),
                    unit="s",
                ),
            ],
        ),
    ),
    DashboardFile(
        name="papergraph-ingestion.json",
        dashboard=dashboard(
            uid="papergraph-ingestion",
            title="PaperGraph Ingestion",
            tags=["papergraph", "ingestion"],
            panels=[
                panel(
                    1,
                    "OpenAlex Articles Returned",
                    "sum(papergraph_openalex_articles_total)",
                    "articles",
                    GRAFANA_GRID_POS(h=8, w=8, x=0, y=0),
                ),
                panel(
                    2,
                    "Vector Papers Uploaded",
                    "sum(papergraph_vector_papers_uploaded_total)",
                    "qdrant",
                    GRAFANA_GRID_POS(h=8, w=8, x=8, y=0),
                ),
                panel(
                    3,
                    "Graph Papers Upserted",
                    "sum(papergraph_graph_papers_upserted_total)",
                    "neo4j",
                    GRAFANA_GRID_POS(h=8, w=8, x=16, y=0),
                ),
                panel(
                    4,
                    "Ingestion Tool Calls",
                    'sum(papergraph_agent_tool_calls_total{tool="ingest_papers"})',
                    "ingest_papers",
                    GRAFANA_GRID_POS(h=8, w=12, x=0, y=8),
                ),
                panel(
                    5,
                    "Ingestion Tool p95 Duration",
                    "histogram_quantile(0.95, sum(papergraph_agent_tool_duration_seconds_bucket{"
                    'tool="ingest_papers"}) by (le))',
                    "p95",
                    GRAFANA_GRID_POS(h=8, w=12, x=12, y=8),
                    unit="s",
                ),
            ],
        ),
    ),
]
