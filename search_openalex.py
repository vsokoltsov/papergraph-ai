"""Search OpenAlex articles by keyword.

Usage:
    python search_openalex.py "graph rag"
"""

from __future__ import annotations

import argparse
import os

import httpx
from dotenv import load_dotenv

def restore_abstract(index):
    if not index:
        return None

    words = {}
    for word, positions in index.items():
        for position in positions:
            words[position] = word

    return " ".join(words[i] for i in sorted(words))


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Search OpenAlex articles by keyword.")
    parser.add_argument("keyword", help="Keyword or phrase to search for.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum number of articles.")
    parser.add_argument(
        "--from-year",
        type=int,
        default=None,
        help="Only include articles from this publication year onward.",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("OPENALEX_API_KEY"),
        help="OpenAlex API key. Defaults to OPENALEX_API_KEY.",
    )
    args = parser.parse_args()

    if not args.api_key:
        parser.error("OpenAlex API key is required. Set OPENALEX_API_KEY or pass --api-key.")

    filters = ["type:article"]
    if args.from_year:
        filters.append(f"from_publication_date:{args.from_year}-01-01")

    response = httpx.get(
        "https://api.openalex.org/works",
        params={
            "api_key": args.api_key,
            "search": args.keyword,
            "filter": ",".join(filters),
            "per-page": args.limit,
        },
        timeout=20,
    )
    response.raise_for_status()

    data = response.json()
    articles = data["results"]

    if len(articles) == 0:
        print("No articles found.")
        return

    print(restore_abstract(articles[0]['abstract_inverted_index']))


if __name__ == "__main__":
    main()
