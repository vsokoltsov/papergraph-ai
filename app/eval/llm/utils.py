from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from app.agents.research import AgentEvent
from app.eval.llm.judge import LangChainLLMJudge
from app.eval.llm.models import AgentAnswerRecord, AgentApproach, EvaluationItem, EvaluationResult
from app.eval.llm.protocols import AgentRunner, LLMJudge
from app.eval.llm.runner import PaperGraphAgentRunner
from app.settings import get_settings

EVALUATION_APPROACHES: list[AgentApproach] = [
    "vector_only",
    "graph_only",
    "vector_plus_graph",
]


def load_dataset(path: Path) -> list[EvaluationItem]:
    """Load LLM evaluation examples from a JSON file.

    Args:
        path: Path to the dataset JSON file.

    Returns:
        Parsed LLM evaluation examples.
    """

    data = json.loads(path.read_text())
    return [
        EvaluationItem(
            question=item["question"],
            answer_orig=item["answer_orig"],
            document=item.get("document"),
        )
        for item in data
    ]


def extract_tool_calls(events: list[AgentEvent]) -> list[dict[str, Any]]:
    """Extract agent tool calls from emitted agent events.

    Args:
        events: Structured agent events emitted during one run.

    Returns:
        Tool call list with tool name and input arguments.
    """

    tool_calls = []
    for event in events:
        match event:
            case {"type": "tool_start", "tool": tool, "input": tool_input}:
                tool_calls.append({"name": tool, "arguments": tool_input})

    return tool_calls


async def generate_agent_answers(
    dataset: list[EvaluationItem],
    runner: AgentRunner,
    approach: AgentApproach,
) -> list[AgentAnswerRecord]:
    """Run the agent for all evaluation questions.

    Args:
        dataset: Ground-truth examples to answer.
        runner: Agent runner implementation.
        approach: Agent approach being evaluated.

    Returns:
        Generated answers with extracted tool trajectories.
    """

    records = []
    for item in dataset:
        agent_result = await runner.run(item.question)
        records.append(
            AgentAnswerRecord(
                approach=approach,
                question=item.question,
                answer_agent=str(agent_result["answer"]),
                answer_orig=item.answer_orig,
                tool_calls=extract_tool_calls(agent_result.get("events", [])),
                document=item.document,
            )
        )

    return records


async def judge_agent_answers(
    records: list[AgentAnswerRecord],
    judge: LLMJudge,
) -> list[EvaluationResult]:
    """Judge generated agent answers and trajectories.

    Args:
        records: Generated agent answers to judge.
        judge: LLM judge implementation.

    Returns:
        Final evaluation results.
    """

    results = []
    for record in records:
        evaluation = await judge.evaluate(record)
        results.append(
            EvaluationResult(
                question=record.question,
                approach=record.approach,
                document=record.document,
                answer_score=evaluation.answer_score,
                trajectory_score=evaluation.trajectory_score,
                answer_reasoning=evaluation.answer_reasoning,
                trajectory_reasoning=evaluation.trajectory_reasoning,
            )
        )

    return results


async def run_evaluation(dataset_path: Path) -> list[EvaluationResult]:
    """Run course-style agent LLM evaluation.

    Args:
        dataset_path: Path to the LLM evaluation dataset.

    Returns:
        Judged answer and trajectory results.
    """

    settings = get_settings()
    dataset = load_dataset(dataset_path)
    records = []
    for approach in EVALUATION_APPROACHES:
        records.extend(
            await generate_agent_answers(
                dataset=dataset,
                runner=PaperGraphAgentRunner(approach=approach),
                approach=approach,
            )
        )

    return await judge_agent_answers(
        records=records,
        judge=LangChainLLMJudge(model_name=settings.LLM_MODEL, api_key=settings.OPENAI_API_KEY),
    )


def results_to_dataframe(results: list[EvaluationResult]) -> pd.DataFrame:
    """Convert LLM evaluation results into a pandas DataFrame.

    Args:
        results: Evaluation results to convert.

    Returns:
        DataFrame with one row per judged answer.
    """

    return pd.DataFrame(
        [
            {
                "approach": result.approach,
                "question": result.question,
                "document": result.document,
                "answer_score": result.answer_score,
                "trajectory_score": result.trajectory_score,
                "answer_reasoning": result.answer_reasoning,
                "trajectory_reasoning": result.trajectory_reasoning,
            }
            for result in results
        ]
    )


def summary_to_dataframe(results: list[EvaluationResult]) -> pd.DataFrame:
    """Convert aggregate LLM evaluation scores into a pandas DataFrame.

    Args:
        results: Evaluation results to summarize.

    Returns:
        Single-row DataFrame with answer and trajectory pass rates.
    """

    rows = []
    for approach in EVALUATION_APPROACHES:
        approach_results = [result for result in results if result.approach == approach]
        total = len(approach_results)
        answer_good = len([result for result in approach_results if result.answer_score == "good"])
        trajectory_good = len(
            [result for result in approach_results if result.trajectory_score == "good"]
        )
        rows.append(
            {
                "approach": approach,
                "total": total,
                "answer_good": answer_good,
                "answer_good_rate": answer_good / total if total else 0.0,
                "trajectory_good": trajectory_good,
                "trajectory_good_rate": trajectory_good / total if total else 0.0,
            }
        )

    return pd.DataFrame(rows).sort_values(
        ["answer_good_rate", "trajectory_good_rate"],
        ascending=False,
    )


def best_result(results: list[EvaluationResult]) -> dict[str, Any]:
    """Select the best LLM approach by answer rate, then trajectory rate.

    Args:
        results: Evaluation results to compare.

    Returns:
        Best approach summary row.
    """

    return summary_to_dataframe(results).to_dict(orient="records")[0]


def render_results(results: list[EvaluationResult], output_format: str = "text") -> str:
    """Render LLM evaluation results for CLI output.

    Args:
        results: Evaluation results to render.
        output_format: One of `text`, `markdown`, or `json`.

    Returns:
        Rendered evaluation output.

    Raises:
        ValueError: If output_format is unsupported.
    """

    best = best_result(results)
    summary = summary_to_dataframe(results)
    details = results_to_dataframe(results)

    match output_format:
        case "json":
            return json.dumps(
                {
                    "best_approach": best["approach"],
                    "summary": summary.to_dict(orient="records"),
                    "results": details.to_dict(orient="records"),
                },
                indent=2,
            )
        case "markdown":
            return "\n\n".join(
                [
                    f"Best LLM approach: `{best['approach']}`",
                    "## LLM Evaluation Summary",
                    summary.to_markdown(index=False, floatfmt=".3f"),
                    "## LLM Evaluation Details",
                    details.to_markdown(index=False),
                ]
            )
        case "text":
            return "\n\n".join(
                [
                    f"Best LLM approach: {best['approach']}",
                    "LLM Evaluation Summary",
                    summary.to_string(index=False, float_format=lambda value: f"{value:.3f}"),
                    "LLM Evaluation Details",
                    details.to_string(index=False),
                ]
            )
        case _:
            raise ValueError(f"Unsupported output format: {output_format}")
