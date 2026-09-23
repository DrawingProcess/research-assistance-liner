"""Scholar validation for wiki Missing Connection candidates.

A missing wikilink is only a candidate. This module asks Scholar whether
A and B already appear together in the literature before a comparison page
is created.
"""
from __future__ import annotations

from src import liner_client

ALREADY_DONE_MIN_HITS = 4
NEEDS_HUMAN_PATH_DEFAULT = "research-gap/gap_needs_human.json"


def validate_gap_pair(page_a: str, page_b: str) -> dict:
    query = f'"{page_a}" AND "{page_b}"'
    result = liner_client.search_scholar(query, max_results=10)
    liner_client.raise_for_status(result, f"search_scholar gap validation for {page_a!r} vs {page_b!r}")
    hits = result.get("response", {}).get("results") or []
    count = len(hits)
    if count >= ALREADY_DONE_MIN_HITS:
        verdict = "already_done"
    elif count == 0:
        verdict = "needs_human"
    else:
        verdict = "underexplored"
    return {"verdict": verdict, "hits": hits, "count": count}
