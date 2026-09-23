# src/wiki_gap_detector.py
"""SCHEMA-native Gap Detector 1 (Missing Connection): scans entities/ and
concepts/ pages tagged research-gap for pairs with enough independent
evidence but no direct connection. Repeated Limitation is handled inline
during canonical page updates (see canonical_pages.create_or_update_page's
body_section parameter, used by daily_pipeline.py), not here.

Detectors 3 (Underexplored Combination) and 4 (Contradiction) remain out
of scope — see the design spec.
"""
from __future__ import annotations

from datetime import date

from src.backlog import slugify
from src.canonical_pages import CANONICAL_DIRS, create_or_update_page, parse_frontmatter, read_page
from src.gap_validator import validate_gap_pair

# Minimum number of distinct sources a single research-gap page must have
# before it is considered "enough evidence" to flag a missing connection
# against another qualifying page (design spec: "pages ... with ≥5 distinct
# sources").
MIN_SOURCES_PER_PAGE = 5

# Comparison creation is uncapped by nature (it scans the whole accumulated
# canonical corpus every run, not just this run's new pages) — bound it so
# one run can't flood the wiki as the corpus grows (Final review, Finding C1).
MAX_NEW_COMPARISONS_PER_RUN = 10


def _research_gap_pages() -> list[dict]:
    pages = []
    for page_type in ("entity", "concept"):
        directory = CANONICAL_DIRS[page_type]
        if not directory.exists():
            continue
        for path in directory.glob("*.md"):
            try:
                fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
            except Exception:
                # Malformed page (e.g. hand-edited block-style YAML, which
                # parse_frontmatter now rejects loudly) — skip just this
                # page, don't let one bad file block gap detection for every
                # other page in the wiki (Final review, Finding I5 part B).
                continue
            if "research-gap" not in fm.get("tags", []):
                continue
            links = {
                line.split("[[", 1)[1].split("]]", 1)[0]
                for line in body.splitlines() if line.strip().startswith("- [[")
            }
            pages.append({
                "slug": path.stem, "title": fm.get("title", path.stem),
                "sources": set(fm.get("sources", [])), "links": links,
            })
    # Directory.glob order is filesystem order, which is not stable as files
    # are added — an order flip would emit "B vs A" where a previous run
    # emitted "A vs B", a different title that the dedup check can't match,
    # creating a near-duplicate page (Final review, Finding I3).
    return sorted(pages, key=lambda p: p["slug"])


def detect_missing_connections(hub_slugs: set[str]) -> list[dict]:
    pages = [p for p in _research_gap_pages() if len(p["sources"]) >= MIN_SOURCES_PER_PAGE]
    candidates = []
    # `pages[i + 1:]` structurally excludes `a` itself, so `a` and `b` can
    # never be the same page here, even if a single page has accumulated
    # wikilinks to multiple hubs over time (see
    # test_detect_missing_connections_never_pairs_a_page_with_itself).
    for i, a in enumerate(pages):
        hubs_a = a["links"] & hub_slugs
        for b in pages[i + 1:]:
            hubs_b = b["links"] & hub_slugs
            if hubs_a & hubs_b:
                continue  # same topic hub — already related, not a "missing" connection
            links_a = a["links"] - hub_slugs
            links_b = b["links"] - hub_slugs
            connected = (b["slug"] in links_a) or (a["slug"] in links_b) or bool(a["sources"] & b["sources"])
            if not connected:
                candidates.append({
                    "page_a": a["title"], "page_b": b["title"],
                    "sources_a": sorted(a["sources"]), "sources_b": sorted(b["sources"]),
                })
    return candidates


def _link_pages(page_a: str, page_b: str, today: date) -> None:
    """already_done: the literature already joins A and B — add wikilinks,
    do not mint a comparison gap page."""
    for title, other in ((page_a, page_b), (page_b, page_a)):
        for page_type in ("entity", "concept"):
            existing = read_page(page_type, title)
            if existing is None:
                continue
            create_or_update_page(
                page_type, title, today, source_path=[],
                wikilinks=[slugify(other)],
                summary=existing[0].get("title", title),
            )
            break


def run_and_create_comparisons(today: date, hub_slugs: set[str]) -> list[str]:
    candidates = detect_missing_connections(hub_slugs)
    candidates.sort(key=lambda c: len(c["sources_a"]) + len(c["sources_b"]), reverse=True)
    created = []
    human_queue: list[dict] = []
    for candidate in candidates:
        if len(created) >= MAX_NEW_COMPARISONS_PER_RUN:
            break
        try:
            title = f"{candidate['page_a']} vs {candidate['page_b']}: underexplored connection"
            if read_page("comparison", title) is not None:
                continue
            try:
                judgement = validate_gap_pair(candidate["page_a"], candidate["page_b"])
            except Exception:
                judgement = {"verdict": "needs_human", "hits": [], "count": 0}
            verdict = judgement.get("verdict")
            if verdict == "already_done":
                _link_pages(candidate["page_a"], candidate["page_b"], today)
                continue
            if verdict != "underexplored":
                human_queue.append({
                    "page_a": candidate["page_a"], "page_b": candidate["page_b"],
                    "count": judgement.get("count", 0),
                })
                continue
            hit_urls = [
                h.get("url") for h in (judgement.get("hits") or []) if h.get("url")
            ]
            body_note = (
                f"Scholar found {judgement.get('count', 0)} joint hit(s); treating as underexplored."
            )
            if hit_urls:
                body_note += " " + "; ".join(hit_urls[:3])
            create_or_update_page(
                "comparison", title, today, source_path=candidate["sources_a"] + candidate["sources_b"],
                wikilinks=[slugify(candidate["page_a"]), slugify(candidate["page_b"])],
                summary=f"Underexplored connection between {candidate['page_a']} and {candidate['page_b']}.",
                body_section=("Scholar check", body_note),
            )
        except Exception:
            continue
        created.append(slugify(title))
    if human_queue:
        from pathlib import Path
        import json
        path = Path("research-gap/gap_needs_human.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"date": today.isoformat(), "candidates": human_queue},
                                   ensure_ascii=False, indent=2), encoding="utf-8")
    return created
