from __future__ import annotations

OPENALEX_URL_PREFIX = "https://openalex.org/"


def normalize_openalex_id(openalex_id: str) -> str:
    """Return a full OpenAlex URL for short or full work IDs.

    Args:
        openalex_id: Short ID like `W123` or full URL like `https://openalex.org/W123`.

    Returns:
        Full OpenAlex work URL.
    """

    if openalex_id.startswith(OPENALEX_URL_PREFIX):
        return openalex_id

    return f"{OPENALEX_URL_PREFIX}{openalex_id}"
