from typing import Any

import httpx

import app.ui as ui
from app.ui import format_event, handle_feedback_submit, run_agent, submit_feedback


def test_format_event_for_run_start() -> None:
    assert (
        format_event(
            {
                "type": "run_start",
                "input": {"question": "graph rag"},
            }
        )
        == "Started research for `graph rag`"
    )


def test_format_event_for_tool_start_with_query() -> None:
    assert (
        format_event(
            {
                "type": "tool_start",
                "tool": "search_openalex",
                "input": {"query": "graph rag", "limit": 5},
            }
        )
        == "Called `search_openalex` with query `graph rag` and limit `5`"
    )


def test_format_event_for_tool_end() -> None:
    assert (
        format_event(
            {
                "type": "tool_end",
                "tool": "search_openalex",
                "output": {"count": 5},
            }
        )
        == "`search_openalex` returned `5` result(s)"
    )


def test_format_event_for_tool_start_with_openalex_ids() -> None:
    assert (
        format_event(
            {
                "type": "tool_start",
                "tool": "get_graph_context",
                "input": {"openalex_ids": ["W1", "W2"]},
            }
        )
        == "Called `get_graph_context` for `2` paper(s)"
    )


def test_format_event_for_unknown_event() -> None:
    assert format_event({"type": "custom_event"}) == "custom_event"


def test_run_agent_posts_question(monkeypatch) -> None:
    fake_client = FakeHttpxClient(
        response={
            "run_id": "run-1",
            "answer": "answer",
            "events": [],
        }
    )
    monkeypatch.setattr(httpx, "Client", lambda timeout: fake_client)

    result = run_agent("http://api/", "What is GraphRAG?")

    assert result == {"run_id": "run-1", "answer": "answer", "events": []}
    assert fake_client.requests == [
        (
            "http://api/agent/runs",
            {"question": "What is GraphRAG?"},
        )
    ]


def test_submit_feedback_posts_feedback(monkeypatch) -> None:
    fake_client = FakeHttpxClient(response={"status": "ok"})
    monkeypatch.setattr(httpx, "Client", lambda timeout: fake_client)

    submit_feedback(
        api_url="http://api/",
        run_id="run-1",
        rating="thumbs_down",
        comment="Missing evidence.",
    )

    assert fake_client.requests == [
        (
            "http://api/feedback",
            {
                "run_id": "run-1",
                "rating": "thumbs_down",
                "comment": "Missing evidence.",
            },
        )
    ]


def test_handle_feedback_submit_records_success(monkeypatch) -> None:
    fake_streamlit = FakeStreamlit()
    monkeypatch.setattr(ui, "st", fake_streamlit)
    monkeypatch.setattr(ui, "submit_feedback", lambda *args: None)

    handle_feedback_submit("http://api", "run-1", "thumbs_up", "")

    assert fake_streamlit.session_state.submitted_feedback == {"run-1"}
    assert fake_streamlit.toasts == ["Feedback submitted"]
    assert fake_streamlit.errors == []


def test_handle_feedback_submit_displays_error(monkeypatch) -> None:
    fake_streamlit = FakeStreamlit()
    monkeypatch.setattr(ui, "st", fake_streamlit)

    def fail_submit_feedback(*args: Any) -> None:
        raise httpx.ConnectError("cannot connect")

    monkeypatch.setattr(ui, "submit_feedback", fail_submit_feedback)

    handle_feedback_submit("http://api", "run-1", "thumbs_down", "Wrong paper.")

    assert fake_streamlit.session_state.submitted_feedback == set()
    assert fake_streamlit.errors == ["Feedback request failed: cannot connect"]


class FakeHttpxResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self.payload


class FakeHttpxClient:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.requests: list[tuple[str, dict[str, Any]]] = []

    def __enter__(self) -> "FakeHttpxClient":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def post(self, url: str, json: dict[str, Any]) -> FakeHttpxResponse:
        self.requests.append((url, json))
        return FakeHttpxResponse(self.response)


class FakeSessionState:
    def __init__(self) -> None:
        self.submitted_feedback: set[str] = set()


class FakeStreamlit:
    def __init__(self) -> None:
        self.session_state = FakeSessionState()
        self.toasts: list[str] = []
        self.errors: list[str] = []

    def toast(self, message: str) -> None:
        self.toasts.append(message)

    def error(self, message: str) -> None:
        self.errors.append(message)
