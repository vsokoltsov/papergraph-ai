from typing import Any

import httpx

import app.ui as ui
from app.ui import (
    append_answer_delta,
    format_event,
    handle_feedback_submit,
    parse_sse_line,
    run_agent,
    run_chat_turn,
    stream_agent,
    submit_feedback,
)


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


def test_stream_agent_yields_sse_events(monkeypatch) -> None:
    fake_client = FakeHttpxClient(
        response={"unused": True},
        stream_lines=[
            'data: {"type": "run_id", "run_id": "run-1"}',
            "",
            'data: {"type": "answer_delta", "delta": "Answer"}',
        ],
    )
    monkeypatch.setattr(httpx, "Client", lambda timeout: fake_client)

    assert list(stream_agent("http://api/", "What is GraphRAG?")) == [
        {"type": "run_id", "run_id": "run-1"},
        {"type": "answer_delta", "delta": "Answer"},
    ]
    assert fake_client.stream_requests == [
        (
            "POST",
            "http://api/agent/runs/stream",
            {"question": "What is GraphRAG?"},
        )
    ]


def test_parse_sse_line_ignores_non_data_lines() -> None:
    assert parse_sse_line("") is None
    assert parse_sse_line("event: message") is None


def test_parse_sse_line_returns_json_payload() -> None:
    assert parse_sse_line('data: {"type": "done"}') == {"type": "done"}


def test_append_answer_delta_adds_spacing() -> None:
    assert append_answer_delta("", "Hello") == "Hello"
    assert append_answer_delta("Hello", "world") == "Hello world"


def test_run_chat_turn_streams_answer_and_saves_message(monkeypatch) -> None:
    fake_streamlit = FakeStreamlit()
    feedback_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(ui, "st", fake_streamlit)
    monkeypatch.setattr(
        ui,
        "stream_agent",
        lambda api_url, question: iter(
            [
                {"type": "run_id", "run_id": "run-1"},
                {
                    "type": "agent_event",
                    "event": {"type": "run_start", "input": {"question": question}},
                },
                {"type": "answer_delta", "delta": "Graph"},
                {"type": "answer_delta", "delta": "RAG"},
                {"type": "done", "run_id": "run-1", "answer": "Graph RAG"},
            ]
        ),
    )
    monkeypatch.setattr(
        ui,
        "render_feedback_form",
        lambda api_url, run_id: feedback_calls.append((api_url, run_id)),
    )

    run_chat_turn("http://api", "What is GraphRAG?")

    assert fake_streamlit.session_state.messages == [
        {"role": "user", "content": "What is GraphRAG?"},
        {
            "role": "assistant",
            "content": "Graph RAG",
            "events": [{"type": "run_start", "input": {"question": "What is GraphRAG?"}}],
            "run_id": "run-1",
        },
    ]
    assert fake_streamlit.status_updates == [
        {"label": "Research complete", "state": "complete"},
    ]
    assert feedback_calls == [("http://api", "run-1")]


def test_run_chat_turn_displays_stream_error(monkeypatch) -> None:
    fake_streamlit = FakeStreamlit()
    monkeypatch.setattr(ui, "st", fake_streamlit)
    monkeypatch.setattr(
        ui,
        "stream_agent",
        lambda api_url, question: iter([{"type": "error", "message": "backend failed"}]),
    )

    run_chat_turn("http://api", "What is GraphRAG?")

    assert fake_streamlit.session_state.messages == [
        {"role": "user", "content": "What is GraphRAG?"}
    ]
    assert fake_streamlit.status_updates == [{"label": "Request failed", "state": "error"}]
    assert fake_streamlit.errors == ["Backend request failed: backend failed"]


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


class FakeHttpxStreamResponse:
    def __init__(self, lines: list[str]) -> None:
        self.lines = lines

    def __enter__(self) -> "FakeHttpxStreamResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    def iter_lines(self) -> list[str]:
        return self.lines


class FakeHttpxClient:
    def __init__(
        self,
        response: dict[str, Any],
        stream_lines: list[str] | None = None,
    ) -> None:
        self.response = response
        self.stream_lines = stream_lines or []
        self.requests: list[tuple[str, dict[str, Any]]] = []
        self.stream_requests: list[tuple[str, str, dict[str, Any]]] = []

    def __enter__(self) -> "FakeHttpxClient":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def post(self, url: str, json: dict[str, Any]) -> FakeHttpxResponse:
        self.requests.append((url, json))
        return FakeHttpxResponse(self.response)

    def stream(self, method: str, url: str, json: dict[str, Any]) -> FakeHttpxStreamResponse:
        self.stream_requests.append((method, url, json))
        return FakeHttpxStreamResponse(self.stream_lines)


class FakeSessionState:
    def __init__(self) -> None:
        self.submitted_feedback: set[str] = set()
        self.messages: list[dict[str, Any]] = []


class FakeContext:
    def __init__(self, streamlit: "FakeStreamlit") -> None:
        self.streamlit = streamlit

    def __enter__(self) -> "FakeContext":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def update(self, **kwargs: str) -> None:
        self.streamlit.status_updates.append(kwargs)


class FakePlaceholder:
    def __init__(self) -> None:
        self.markdown_calls: list[str] = []

    def markdown(self, value: str) -> None:
        self.markdown_calls.append(value)


class FakeStreamlit:
    def __init__(self) -> None:
        self.session_state = FakeSessionState()
        self.toasts: list[str] = []
        self.errors: list[str] = []
        self.markdown_calls: list[str] = []
        self.status_updates: list[dict[str, str]] = []

    def chat_message(self, role: str) -> FakeContext:
        return FakeContext(self)

    def status(self, label: str, expanded: bool) -> FakeContext:
        return FakeContext(self)

    def empty(self) -> FakePlaceholder:
        return FakePlaceholder()

    def markdown(self, value: str) -> None:
        self.markdown_calls.append(value)

    def toast(self, message: str) -> None:
        self.toasts.append(message)

    def error(self, message: str) -> None:
        self.errors.append(message)
