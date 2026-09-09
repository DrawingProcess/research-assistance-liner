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


def run_and_create_comparisons(today: date, hub_slugs: set[str]) -> list[str]:
    candidates = detect_missing_connections(hub_slugs)
    # Rank by total evidence so the highest-confidence gaps win the per-run
    # budget; the rest are simply reconsidered next run (detection re-scans
    # the whole corpus every time, so deferring loses nothing).
    candidates.sort(key=lambda c: len(c["sources_a"]) + len(c["sources_b"]), reverse=True)
    created = []
    for candidate in candidates:
        if len(created) >= MAX_NEW_COMPARISONS_PER_RUN:
            break  # candidates are sorted by evidence descending; remaining ones are lower priority
        # Per-candidate isolation, mirroring _research_gap_pages' per-file
        # isolation: one malformed pre-existing comparisons/ file must not
        # raise out of the loop and cost every other candidate its creation
        # for the whole run (re-review, Minor 2).
        try:
            title = f"{candidate['page_a']} vs {candidate['page_b']}: underexplored connection"
            if read_page("comparison", title) is not None:
                continue  # already exists — doesn't consume this run's new-page budget
            # The full evidence base, not just the first source — a
            # comparison page used to store exactly one of the (often 10+)
            # sources that actually justified the pairing, understating how
            # well-evidenced the flagged gap really is (create_or_update_page
            # now accepts a list in one call, so this doesn't cost N
            # separate file/index/log writes).
            create_or_update_page(
                "comparison", title, today, source_path=candidate["sources_a"] + candidate["sources_b"],
                wikilinks=[slugify(candidate["page_a"]), slugify(candidate["page_b"])],
                summary=f"Underexplored connection between {candidate['page_a']} and {candidate['page_b']}.",
            )
        except Exception:
            continue
        created.append(slugify(title))
    return created
