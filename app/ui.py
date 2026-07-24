import json
from collections.abc import Iterator
from typing import Any, Literal

import httpx
import streamlit as st

from app.settings import get_settings


def main() -> None:
    settings = get_settings()

    st.set_page_config(
        page_title="PaperGraph AI",
        page_icon="PG",
        layout="wide",
    )
    st.title("PaperGraph AI")

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "submitted_feedback" not in st.session_state:
        st.session_state.submitted_feedback = set()

    if not st.session_state.messages and handle_question_form(settings.API_URL):
        return

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "assistant" and message.get("events"):
                render_events(message["events"])
            st.markdown(message["content"])
            if message["role"] == "assistant" and message.get("run_id"):
                render_feedback_form(settings.API_URL, message["run_id"])

    if st.session_state.messages:
        handle_question_form(settings.API_URL)


def handle_question_form(api_url: str) -> bool:
    with st.form("question_form", clear_on_submit=True):
        question = st.text_input(
            "Ask about papers, topics, authors, or graph relationships",
            placeholder="Find papers about graph rag and explain the main research directions",
        )
        submitted = st.form_submit_button("Send")

    if submitted and question:
        run_chat_turn(api_url, question)
        return True

    return False


def run_chat_turn(api_url: str, question: str) -> None:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        answer = ""
        events: list[dict[str, Any]] = []
        run_id = ""
        research_placeholder = st.empty()
        answer_placeholder = st.empty()
        status_label = "Still working"
        render_research_placeholder(research_placeholder, status_label, events)

        try:
            for stream_event in stream_agent(api_url, question):
                match stream_event:
                    case {"type": "run_id", "run_id": value}:
                        run_id = value
                    case {"type": "status"}:
                        continue
                    case {"type": "agent_event", "event": event}:
                        append_visible_event(events, event)
                        render_research_placeholder(research_placeholder, status_label, events)
                    case {"type": "answer_delta", "delta": delta}:
                        answer = append_answer_delta(answer, delta)
                        answer_placeholder.markdown(answer)
                    case {"type": "done", "run_id": value, "answer": final_answer}:
                        run_id = value
                        answer = final_answer
                        answer_placeholder.markdown(answer)
                    case {"type": "error", "message": message}:
                        raise httpx.HTTPError(message)
        except httpx.HTTPError as error:
            render_research_placeholder(
                research_placeholder,
                "Request failed",
                events,
                state="error",
            )
            st.error(f"Backend request failed: {error}")
            return

        render_research_placeholder(
            research_placeholder,
            "Research complete",
            events,
            state="complete",
            expanded=True,
        )

        assistant_message = {
            "role": "assistant",
            "content": answer,
            "events": events,
            "run_id": run_id,
        }
        st.session_state.messages.append(assistant_message)
        render_feedback_form(api_url, run_id)


def run_agent(api_url: str, question: str) -> dict[str, Any]:
    with httpx.Client(timeout=120) as client:
        response = client.post(
            f"{api_url.rstrip('/')}/agent/runs",
            json={"question": question},
        )
        response.raise_for_status()
        return response.json()


def stream_agent(api_url: str, question: str) -> Iterator[dict[str, Any]]:
    with httpx.Client(timeout=120) as client:
        with client.stream(
            "POST",
            f"{api_url.rstrip('/')}/agent/runs/stream",
            json={"question": question},
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                event = parse_sse_line(line)
                if event:
                    yield event


def parse_sse_line(line: str) -> dict[str, Any] | None:
    if not line.startswith("data: "):
        return None

    return json.loads(line.removeprefix("data: "))


def append_answer_delta(answer: str, delta: str) -> str:
    if not answer:
        return delta

    return f"{answer} {delta}"


def append_visible_event(events: list[dict[str, Any]], event: dict[str, Any]) -> None:
    if events and format_event(events[-1]) == format_event(event):
        return

    events.append(event)


def submit_feedback(
    api_url: str,
    run_id: str,
    rating: str,
    comment: str | None = None,
) -> None:
    with httpx.Client(timeout=30) as client:
        response = client.post(
            f"{api_url.rstrip('/')}/feedback",
            json={
                "run_id": run_id,
                "rating": rating,
                "comment": comment,
            },
        )
        response.raise_for_status()


def render_feedback_form(api_url: str, run_id: str) -> None:
    if not run_id:
        return

    if run_id in st.session_state.submitted_feedback:
        st.caption("Feedback submitted")
        return

    st.caption("Was this answer useful?")
    comment = st.text_input(
        "Optional feedback comment",
        key=f"feedback_comment_{run_id}",
        placeholder="What was useful or missing?",
    )
    left, right = st.columns(2)

    with left:
        if st.button("Useful", key=f"feedback_up_{run_id}", help="Mark answer as useful"):
            handle_feedback_submit(api_url, run_id, "thumbs_up", comment)

    with right:
        if st.button("Not useful", key=f"feedback_down_{run_id}", help="Mark answer as not useful"):
            handle_feedback_submit(api_url, run_id, "thumbs_down", comment)


def handle_feedback_submit(
    api_url: str,
    run_id: str,
    rating: str,
    comment: str | None,
) -> None:
    try:
        submit_feedback(api_url, run_id, rating, comment or None)
    except httpx.HTTPError as error:
        st.error(f"Feedback request failed: {error}")
        return

    st.session_state.submitted_feedback.add(run_id)
    st.toast("Feedback submitted")


def render_events(events: list[dict[str, Any]]) -> None:
    if not events:
        return

    render_research_block("Research complete", events, state="complete", expanded=True)


def render_events_placeholder(placeholder: Any, events: list[dict[str, Any]]) -> None:
    if not events:
        return

    placeholder.markdown(render_event_lines_markdown(events))


def render_research_placeholder(
    placeholder: Any,
    label: str,
    events: list[dict[str, Any]],
    state: Literal["running", "complete", "error"] = "running",
    expanded: bool = True,
) -> None:
    with placeholder.container():
        render_research_block(label, events, state=state, expanded=expanded)


def render_research_block(
    label: str,
    events: list[dict[str, Any]],
    state: Literal["running", "complete", "error"],
    expanded: bool,
) -> None:
    with st.status(label, state=state, expanded=expanded):
        if state == "running":
            st.progress(running_progress_value(events), text="Research in progress...")

        if events:
            render_event_lines(events)
        else:
            st.caption("Waiting for agent events...")


def running_progress_value(events: list[dict[str, Any]]) -> int:
    if not events:
        return 10

    return min(90, 20 + (len(deduplicate_visible_events(events)) * 10))


def render_event_lines(events: list[dict[str, Any]]) -> None:
    st.markdown(render_event_lines_markdown(events))


def render_event_lines_markdown(events: list[dict[str, Any]]) -> str:
    lines = [
        "Agent steps",
        *[f"- {format_event(event)}" for event in deduplicate_visible_events(events)],
    ]
    return "\n".join(lines)


def deduplicate_visible_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    visible_events: list[dict[str, Any]] = []
    for event in events:
        append_visible_event(visible_events, event)

    return visible_events


def format_event(event: dict[str, Any]) -> str:
    match event["type"]:
        case "run_start":
            question = event["input"]["question"]
            return f"Started research for `{question}`"
        case "run_end":
            return "Prepared final answer"
        case "tool_start":
            return format_tool_start(event)
        case "tool_end":
            tool = event["tool"]
            count = event["output"]["count"]
            return f"`{tool}` returned `{count}` result(s)"
        case _:
            return event["type"]


def format_tool_start(event: dict[str, Any]) -> str:
    tool = event["tool"]
    tool_input = event["input"]

    match tool_input:
        case {"query": query, "limit": limit}:
            return f"Called `{tool}` with query `{query}` and limit `{limit}`"
        case {"openalex_ids": openalex_ids}:
            return f"Called `{tool}` for `{len(openalex_ids)}` paper(s)"
        case _:
            return f"Called `{tool}`"


if __name__ == "__main__":
    main()
