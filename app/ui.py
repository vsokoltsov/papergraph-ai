from typing import Any

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
            st.markdown(message["content"])
            if message["role"] == "assistant" and message.get("events"):
                render_events(message["events"])
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
        with st.status("Researching", expanded=True) as status:
            try:
                result = run_agent(api_url, question)
            except httpx.HTTPError as error:
                status.update(label="Request failed", state="error")
                st.error(f"Backend request failed: {error}")
                return

            render_events(result["events"])
            status.update(label="Research complete", state="complete")

        st.markdown(result["answer"])
        render_feedback_form(api_url, result["run_id"])

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": result["answer"],
            "events": result["events"],
            "run_id": result["run_id"],
        }
    )


def run_agent(api_url: str, question: str) -> dict[str, Any]:
    with httpx.Client(timeout=120) as client:
        response = client.post(
            f"{api_url.rstrip('/')}/agent/runs",
            json={"question": question},
        )
        response.raise_for_status()
        return response.json()


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
    if run_id in st.session_state.submitted_feedback:
        st.caption("Feedback submitted")
        return

    comment = st.text_input(
        "Optional feedback comment",
        key=f"feedback_comment_{run_id}",
        placeholder="What was useful or missing?",
    )
    left, right = st.columns(2)

    with left:
        if st.button("Thumbs up", key=f"feedback_up_{run_id}"):
            handle_feedback_submit(api_url, run_id, "thumbs_up", comment)

    with right:
        if st.button("Thumbs down", key=f"feedback_down_{run_id}"):
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

    st.caption("Agent steps")
    for event in events:
        st.markdown(f"- {format_event(event)}")


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
