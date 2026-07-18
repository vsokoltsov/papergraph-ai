from __future__ import annotations

import argparse
import asyncio
import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import cast

from app.eval.llm.models import AgentApproach
from app.eval.llm.utils import EVALUATION_APPROACHES, render_results, run_evaluation_for_approaches


async def main() -> None:
    """Parse CLI arguments and print LLM evaluation results."""

    parser = argparse.ArgumentParser(description="Evaluate PaperGraph agent answers.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path(__file__).with_name("llm_dataset.json"),
    )
    parser.add_argument(
        "--output-format",
        choices=["text", "markdown", "json"],
        default="text",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Write llm-eval.md and llm-eval.json from a single evaluation run.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of dataset examples to evaluate.",
    )
    parser.add_argument(
        "--approaches",
        nargs="+",
        choices=EVALUATION_APPROACHES,
        default=EVALUATION_APPROACHES,
        help="Agent approaches to evaluate.",
    )
    args = parser.parse_args()

    with redirect_stdout(sys.stderr):
        results = await run_evaluation_for_approaches(
            dataset_path=args.dataset,
            approaches=[cast(AgentApproach, approach) for approach in args.approaches],
            limit=args.limit,
        )

    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "llm-eval.md").write_text(
            render_results(results, output_format="markdown")
        )
        (args.output_dir / "llm-eval.json").write_text(
            render_results(results, output_format="json")
        )
        print(render_results(results, output_format=args.output_format))
        return

    print(render_results(results, output_format=args.output_format))


if __name__ == "__main__":
    asyncio.run(main())
