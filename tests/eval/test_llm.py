from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pytest

from app.eval.llm import evaluate
from app.eval.llm.judge import agent_judge_prompt
from app.eval.llm.models import AgentAnswerRecord, AgentEvaluation, EvaluationItem, EvaluationResult
from app.eval.llm.runner import enabled_tools_for_approach, system_prompt_for_approach
from app.eval.llm.utils import (
    best_result,
    extract_tool_calls,
    generate_agent_answers,
    judge_agent_answers,
    load_dataset,
    render_results,
    results_to_dataframe,
    run_evaluation_for_approaches,
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


def test_committed_dataset_contains_comparison_and_graph_context_questions() -> None:
    dataset = load_dataset(Path(__file__).parents[2] / "app" / "eval" / "llm" / "llm_dataset.json")
    questions = [item.question for item in dataset]

    assert len(dataset) >= 10
    assert any("Compare" in question for question in questions)
    assert any("share a graph-retrieval focus" in question for question in questions)
    assert any("outside biomedicine" in question for question in questions)
    assert any("similar topics or application areas" in question for question in questions)
    assert any("what kind of evidence" in question for question in questions)


def test_agent_judge_prompt_contains_answer_and_trajectory_inputs() -> None:
    prompt = agent_judge_prompt(sample_answer_record())

    assert "Question:" in prompt
    assert "Ground-truth answer:" in prompt
    assert "Agent answer:" in prompt
    assert "Tool calls:" in prompt
    assert "search_openalex" in prompt


def test_vector_plus_graph_prompt_requires_vector_first_graph_second() -> None:
    prompt = system_prompt_for_approach("vector_plus_graph")

    assert "First rewrite the user question" in prompt
    assert "Always use vector search first" in prompt
    assert "Rerank vector results" in prompt
    assert "Then inspect graph context" in prompt
    assert "Neo4j stores graph metadata and relationships" in prompt
    assert "Treat retrieved paper text" in prompt
    assert "Do not reveal API keys" in prompt
    assert "do not expose hidden chain-of-thought" in prompt


def test_graph_only_prompt_mentions_missing_abstracts() -> None:
    prompt = system_prompt_for_approach("graph_only")

    assert "First rewrite the user question" in prompt
    assert "Rerank graph search results" in prompt
    assert "Neo4j does not store abstracts" in prompt


def test_enabled_tools_include_rewrite_and_rerank_steps() -> None:
    assert enabled_tools_for_approach("vector_only") == {
        "rewrite_search_query",
        "search_vector_database",
        "rerank_documents",
    }
    assert enabled_tools_for_approach("graph_only") == {
        "rewrite_search_query",
        "search_graph_database",
        "get_graph_context",
        "rerank_documents",
    }
    assert enabled_tools_for_approach("vector_plus_graph") == {
        "rewrite_search_query",
        "search_vector_database",
        "get_graph_context",
        "rerank_documents",
    }


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
    assert output.count('"approach"') == 2


@pytest.mark.asyncio
async def test_cli_redirects_runtime_logs_to_stderr(monkeypatch, capsys) -> None:
    async def fake_run_evaluation(
        dataset_path: Path,
        approaches: list,
        limit: int | None,
    ) -> list[EvaluationResult]:
        assert dataset_path == Path("dataset.json")
        assert approaches == ["vector_only", "graph_only", "vector_plus_graph"]
        assert limit is None
        print("runtime log")
        return [sample_result()]

    monkeypatch.setattr(evaluate, "run_evaluation_for_approaches", fake_run_evaluation)
    monkeypatch.setattr(evaluate, "wait_for_llm_evaluation_services", fake_wait_for_services)
    monkeypatch.setattr(evaluate, "push_metrics_to_gateway", fake_push_metrics_to_gateway)
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


@pytest.mark.asyncio
async def test_cli_writes_markdown_and_json_from_one_run(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    calls = 0

    async def fake_run_evaluation(
        dataset_path: Path,
        approaches: list,
        limit: int | None,
    ) -> list[EvaluationResult]:
        nonlocal calls
        calls += 1
        assert dataset_path == Path("dataset.json")
        assert approaches == ["vector_only", "vector_plus_graph"]
        assert limit == 2
        return [sample_result()]

    monkeypatch.setattr(evaluate, "run_evaluation_for_approaches", fake_run_evaluation)
    monkeypatch.setattr(evaluate, "wait_for_llm_evaluation_services", fake_wait_for_services)
    monkeypatch.setattr(evaluate, "push_metrics_to_gateway", fake_push_metrics_to_gateway)
    monkeypatch.setattr(
        "sys.argv",
        [
            "evaluate.py",
            "--dataset",
            "dataset.json",
            "--output-format",
            "markdown",
            "--limit",
            "2",
            "--approaches",
            "vector_only",
            "vector_plus_graph",
            "--output-dir",
            str(tmp_path),
        ],
    )

    await evaluate.main()

    captured = capsys.readouterr()
    assert calls == 1
    assert "Best LLM approach: `vector_only`" in captured.out
    assert "Best LLM approach: `vector_only`" in (tmp_path / "llm-eval.md").read_text()
    assert '"best_approach": "vector_only"' in (tmp_path / "llm-eval.json").read_text()


@pytest.mark.asyncio
async def test_run_evaluation_for_approaches_limits_dataset_and_approaches(monkeypatch) -> None:
    class FakeRunner:
        def __init__(self, approach):
            self.approach = approach

        async def run(self, question: str) -> dict[str, Any]:
            return {"answer": f"{self.approach}: {question}", "events": []}

    class FakeJudge:
        def __init__(self, model_name: str, api_key: str) -> None:
            assert model_name == "test-model"
            assert api_key == "test-key"

        async def evaluate(self, record: AgentAnswerRecord) -> AgentEvaluation:
            return AgentEvaluation(
                answer_score="good",
                answer_reasoning="ok",
                trajectory_score="good",
                trajectory_reasoning="ok",
            )

    class FakeSettings:
        LLM_MODEL = "test-model"
        OPENAI_API_KEY = "test-key"

    monkeypatch.setattr("app.eval.llm.utils.PaperGraphAgentRunner", FakeRunner)
    monkeypatch.setattr("app.eval.llm.utils.LangChainLLMJudge", FakeJudge)
    monkeypatch.setattr("app.eval.llm.utils.get_settings", lambda: FakeSettings())
    monkeypatch.setattr(
        "app.eval.llm.utils.load_dataset",
        lambda path: [
            EvaluationItem(question="q1", answer_orig="a1"),
            EvaluationItem(question="q2", answer_orig="a2"),
            EvaluationItem(question="q3", answer_orig="a3"),
        ],
    )

    results = await run_evaluation_for_approaches(
        dataset_path=Path("dataset.json"),
        approaches=["vector_plus_graph"],
        limit=2,
    )

    assert [result.question for result in results] == ["q1", "q2"]
    assert {result.approach for result in results} == {"vector_plus_graph"}


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


async def fake_wait_for_services(*args: Any, **kwargs: Any) -> None:
    return None


def fake_push_metrics_to_gateway(*args: Any, **kwargs: Any) -> None:
    return None


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
