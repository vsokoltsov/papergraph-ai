"""Search OpenAlex articles by keyword.

Usage:
    python search_openalex.py "graph rag"
"""

from __future__ import annotations

import argparse
from app.settings import get_settings
from app.clients.openalex import OpenAlexClient

def restore_abstract(index):
    if not index:
        return None

    words = {}
    for word, positions in index.items():
        for position in positions:
            words[position] = word

    return " ".join(words[i] for i in sorted(words))


def main() -> None:
    settings = get_settings()

    parser = argparse.ArgumentParser(description="Search OpenAlex articles by keyword.")
    parser.add_argument("keyword", help="Keyword or phrase to search for.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum number of articles.")
    parser.add_argument(
        "--from-year",
        type=int,
        default=None,
        help="Only include articles from this publication year onward.",
    )
    args = parser.parse_args()
    openalex_client = OpenAlexClient(
        api_key=settings.OPENALEX_API_KEY
    )
    articles = openalex_client.get_articles(
        query=args.keyword,
        limit=args.limit
    )

    if len(articles) == 0:
        print("No articles found.")
        return

    print(restore_abstract(articles[0].abstract_inverted_index))


if __name__ == "__main__":
    main()
