from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pytest

from app.eval.llm import evaluate
from app.eval.llm.judge import agent_judge_prompt
from app.eval.llm.models import AgentAnswerRecord, AgentEvaluation, EvaluationItem, EvaluationResult
from app.eval.llm.utils import (
    best_result,
    extract_tool_calls,
    generate_agent_answers,
    judge_agent_answers,
    render_results,
    results_to_dataframe,
    summary_to_dataframe,
)


def test_extract_tool_calls_keeps_tool_name_and_arguments() -> None:
    tool_calls = extract_tool_calls(
        [
            {"type": "run_start", "input": {"question": "graph rag"}},
            {
                "type": "tool_start",
                "tool": "search_vector_database",
                "input": {"query": "graph rag", "limit": 5},
            },
            {
                "type": "tool_end",
                "tool": "search_vector_database",
                "output": {"count": 2},
            },
        ]
    )

    assert tool_calls == [
        {
            "name": "search_vector_database",
            "arguments": {"query": "graph rag", "limit": 5},
        }
    ]


def test_agent_judge_prompt_contains_answer_and_trajectory_inputs() -> None:
    prompt = agent_judge_prompt(sample_answer_record())

    assert "Question:" in prompt
    assert "Ground-truth answer:" in prompt
    assert "Agent answer:" in prompt
    assert "Tool calls:" in prompt
    assert "search_openalex" in prompt


@pytest.mark.asyncio
async def test_generate_agent_answers_runs_agent_and_extracts_tool_calls() -> None:
    records = await generate_agent_answers(
        dataset=[
            EvaluationItem(
                question="Explain Graph RAG.",
                answer_orig="Expected answer.",
                document="doc-1",
            )
        ],
        runner=FakeAgentRunner(),
        approach="vector_only",
    )

    assert records == [
        AgentAnswerRecord(
            approach="vector_only",
            question="Explain Graph RAG.",
            answer_agent="Agent answer.",
            answer_orig="Expected answer.",
            document="doc-1",
            tool_calls=[
                {
                    "name": "search_openalex",
                    "arguments": {"query": "graph rag", "limit": 5},
                }
            ],
        )
    ]


@pytest.mark.asyncio
async def test_judge_agent_answers_returns_structured_results() -> None:
    results = await judge_agent_answers(
        records=[sample_answer_record()],
        judge=FakeJudge(),
    )

    assert results == [
        EvaluationResult(
            approach="vector_only",
            question="Explain Graph RAG.",
            document="doc-1",
            answer_score="good",
            trajectory_score="good",
            answer_reasoning="The answer matches the expected points.",
            trajectory_reasoning="The tool call was relevant.",
        )
    ]


def test_summary_to_dataframe_calculates_pass_rates() -> None:
    dataframe = summary_to_dataframe(
        [
            sample_result(answer_score="good", trajectory_score="good"),
            sample_result(answer_score="bad", trajectory_score="good"),
        ]
    )

    assert dataframe.to_dict(orient="records") == [
        {
            "approach": "vector_only",
            "total": 2,
            "answer_good": 1,
            "answer_good_rate": 0.5,
            "trajectory_good": 2,
            "trajectory_good_rate": 1.0,
        },
        {
            "approach": "graph_only",
            "total": 0,
            "answer_good": 0,
            "answer_good_rate": 0.0,
            "trajectory_good": 0,
            "trajectory_good_rate": 0.0,
        },
        {
            "approach": "vector_plus_graph",
            "total": 0,
            "answer_good": 0,
            "answer_good_rate": 0.0,
            "trajectory_good": 0,
            "trajectory_good_rate": 0.0,
        },
    ]


def test_best_result_uses_answer_rate_then_trajectory_rate() -> None:
    assert (
        best_result(
            [
                sample_result(
                    approach="vector_only",
                    answer_score="good",
                    trajectory_score="bad",
                ),
                sample_result(
                    approach="vector_plus_graph",
                    answer_score="good",
                    trajectory_score="good",
                ),
            ]
        )["approach"]
        == "vector_plus_graph"
    )


def test_results_to_dataframe_returns_detail_rows() -> None:
    dataframe = results_to_dataframe([sample_result()])

    assert dataframe["approach"].to_list() == ["vector_only"]
    assert dataframe["answer_score"].to_list() == ["good"]
    assert dataframe["trajectory_score"].to_list() == ["good"]


def test_render_results_as_text() -> None:
    output = render_results([sample_result()], output_format="text")

    assert "Best LLM approach: vector_only" in output
    assert "LLM Evaluation Summary" in output
    assert "answer_good_rate" in output
    assert "LLM Evaluation Details" in output


def test_render_results_as_markdown() -> None:
    output = render_results([sample_result()], output_format="markdown")

    assert "Best LLM approach: `vector_only`" in output
    assert "## LLM Evaluation Summary" in output
    assert "| approach" in output
    assert "## LLM Evaluation Details" in output


def test_render_results_as_json() -> None:
    output = render_results([sample_result()], output_format="json")

    assert '"best_approach": "vector_only"' in output
    assert '"summary"' in output
    assert '"results"' in output
    assert '"answer_score": "good"' in output
    assert output.count('"approach"') == 4


@pytest.mark.asyncio
async def test_cli_redirects_runtime_logs_to_stderr(monkeypatch, capsys) -> None:
    async def fake_run_evaluation(dataset_path: Path) -> list[EvaluationResult]:
        assert dataset_path == Path("dataset.json")
        print("runtime log")
        return [sample_result()]

    monkeypatch.setattr(evaluate, "run_evaluation", fake_run_evaluation)
    monkeypatch.setattr(
        "sys.argv",
        [
            "evaluate.py",
            "--dataset",
            "dataset.json",
            "--output-format",
            "json",
        ],
    )

    await evaluate.main()

    captured = capsys.readouterr()
    assert "runtime log" in captured.err
    assert "runtime log" not in captured.out
    assert captured.out.lstrip().startswith("{")


def sample_answer_record() -> AgentAnswerRecord:
    return AgentAnswerRecord(
        approach="vector_only",
        question="Explain Graph RAG.",
        answer_agent="Agent answer.",
        answer_orig="Expected answer.",
        document="doc-1",
        tool_calls=[
            {
                "name": "search_openalex",
                "arguments": {"query": "graph rag", "limit": 5},
            }
        ],
    )


def sample_result(
    approach: Literal["vector_only", "graph_only", "vector_plus_graph"] = "vector_only",
    answer_score: Literal["good", "bad"] = "good",
    trajectory_score: Literal["good", "bad"] = "good",
) -> EvaluationResult:
    return EvaluationResult(
        approach=approach,
        question="Explain Graph RAG.",
        document="doc-1",
        answer_score=answer_score,
        trajectory_score=trajectory_score,
        answer_reasoning="The answer matches the expected points.",
        trajectory_reasoning="The tool call was relevant.",
    )


@dataclass
class FakeAgentRunner:
    async def run(self, question: str) -> dict[str, Any]:
        assert question == "Explain Graph RAG."
        return {
            "answer": "Agent answer.",
            "events": [
                {
                    "type": "tool_start",
                    "tool": "search_openalex",
                    "input": {"query": "graph rag", "limit": 5},
                }
            ],
        }


@dataclass
class FakeJudge:
    async def evaluate(self, record: AgentAnswerRecord) -> AgentEvaluation:
        assert record.question == "Explain Graph RAG."
        return AgentEvaluation(
            answer_score="good",
            answer_reasoning="The answer matches the expected points.",
            trajectory_score="good",
            trajectory_reasoning="The tool call was relevant.",
        )
