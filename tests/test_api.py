from typing import Any

from fastapi.testclient import TestClient

from app.api import create_app


def test_health_returns_ok() -> None:
    app = create_app(agent_runner=_fake_agent_runner)
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_agent_runs_endpoint_returns_answer_and_events() -> None:
    app = create_app(agent_runner=_fake_agent_runner)
    client = TestClient(app)

    response = client.post(
        "/agent/runs",
        json={"question": "Find graph rag papers"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "Graph RAG answer",
        "events": [
            {
                "type": "run_start",
                "input": {"question": "Find graph rag papers"},
            },
            {
                "type": "run_end",
                "output": {"answer": "Graph RAG answer"},
            },
        ],
    }


def test_metrics_endpoint_exposes_prometheus_metrics() -> None:
    app = create_app(agent_runner=_fake_agent_runner)
    client = TestClient(app)

    client.get("/health")
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "papergraph_http_requests_total" in response.text


async def _fake_agent_runner(question: str) -> dict[str, Any]:
    return {
        "answer": "Graph RAG answer",
        "events": [
            {"type": "run_start", "input": {"question": question}},
            {"type": "run_end", "output": {"answer": "Graph RAG answer"}},
        ],
    }
