"""Year filtering for Scholar Search results. Venue filtering was removed
2026-08-04 after two broken iterations (dropped ~100% of real papers, then
over-rejected ~58% of already-extracted ones) — see
docs/superpowers/specs/2026-08-03-research-gap-daily-pipeline-design.md
"What changed" section.
"""
from __future__ import annotations

import re
from datetime import date

YEARS_WINDOW = 5


def paper_year(paper: dict) -> int | None:
    raw_date = paper.get("date") or ""
    match = re.match(r"(\d{4})", raw_date)
    return int(match.group(1)) if match else None


def filter_papers(papers: list[dict], today: date) -> dict:
    min_year = today.year - YEARS_WINDOW
    kept: list[dict] = []
    dropped_year = 0
    for paper in papers:
        year = paper_year(paper)
        if year is None or year < min_year:
            dropped_year += 1
            continue
        kept.append(paper)
    return {"kept": kept, "dropped_year": dropped_year}
