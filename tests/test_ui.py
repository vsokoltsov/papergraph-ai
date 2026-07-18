from app.ui import format_event


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
