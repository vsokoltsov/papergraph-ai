from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from app.eval.llm.ground_truth.generator import LangChainGroundTruthGenerator
from app.eval.llm.ground_truth.utils import (
    generate_ground_truth,
    load_source_documents,
    save_dataset,
)
from app.settings import get_settings


async def main() -> None:
    """Parse CLI arguments and generate an LLM evaluation dataset."""

    parser = argparse.ArgumentParser(description="Generate LLM evaluation ground truth.")
    parser.add_argument("--source", choices=["qdrant", "json"], default="qdrant")
    parser.add_argument("--input", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name("ground_truth_dataset.json"),
    )
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--questions-per-document", type=int, default=3)
    args = parser.parse_args()

    settings = get_settings()
    documents = await load_source_documents(
        source=args.source,
        input_path=args.input,
        limit=args.limit,
    )
    dataset = await generate_ground_truth(
        documents=documents,
        generator=LangChainGroundTruthGenerator(
            model_name=settings.LLM_MODEL,
            api_key=settings.OPENAI_API_KEY,
        ),
        questions_per_document=args.questions_per_document,
    )
    save_dataset(dataset=dataset, output_path=args.output)
    print(f"Generated {len(dataset)} evaluation examples in {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
