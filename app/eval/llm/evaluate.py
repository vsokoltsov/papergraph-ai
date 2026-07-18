from __future__ import annotations

import argparse
import asyncio
import sys
from contextlib import redirect_stdout
from pathlib import Path

from app.eval.llm.utils import render_results, run_evaluation


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
    args = parser.parse_args()

    with redirect_stdout(sys.stderr):
        results = await run_evaluation(dataset_path=args.dataset)

    print(render_results(results, output_format=args.output_format))


if __name__ == "__main__":
    asyncio.run(main())
