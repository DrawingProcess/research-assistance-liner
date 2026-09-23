# test/test_wiki_gap_detector.py
from datetime import date

import json
import pytest

from src.backlog import slugify
from src.canonical_pages import create_or_update_page, read_page
from src.wiki_gap_detector import (
    MAX_NEW_COMPARISONS_PER_RUN,
    _research_gap_pages,
    detect_missing_connections,
    run_and_create_comparisons,
)

UNDEREXPLORED = {"verdict": "underexplored", "hits": [{"title": "Joint", "url": "https://arxiv.org/abs/1"}], "count": 1}


@pytest.fixture(autouse=True)
def underexplored(monkeypatch):
    monkeypatch.setattr("src.wiki_gap_detector.validate_gap_pair", lambda a, b: UNDEREXPLORED)

INDEX_TEMPLATE = """# Wiki Index

> Total pages: 0

## Entities

## Concepts

## Comparisons

## Queries
"""


def _seed_wiki(tmp_path):
    (tmp_path / "index.md").write_text(INDEX_TEMPLATE, encoding="utf-8")
    (tmp_path / "log.md").write_text("# Wiki Log\n\n", encoding="utf-8")


def _make_area(prefix, n, hub_slug, sources_per_page=5):
    # Each of the `n` pages is accumulated via `sources_per_page` separate
    # create_or_update_page calls (same title, distinct source_path each
    # time), so every page ends up with `sources_per_page` distinct sources
    # of its own — matching the design spec's "pages with >=5 distinct
    # sources" threshold (a per-page property, not a per-hub page count).
    for i in range(n):
        for j in range(sources_per_page):
            create_or_update_page(
                "concept", f"{prefix} Problem {i}", date(2026, 8, 4),
                source_path=f"raw/paper/{prefix}-{i}-{j}.md", wikilinks=[hub_slug], summary="x",
            )


def test_detect_missing_connections_flags_disjoint_areas_with_enough_sources(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    _make_area("AreaA", 5, "area-a")
    _make_area("AreaB", 5, "area-b")

    candidates = detect_missing_connections(hub_slugs={"area-a", "area-b"})
    assert len(candidates) == 5 * 5  # every AreaA page paired with every AreaB page, none share sources/links


def test_detect_missing_connections_skips_pages_below_source_threshold(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    _make_area("AreaA", 2, "area-a", sources_per_page=2)
    _make_area("AreaB", 2, "area-b", sources_per_page=2)

    assert detect_missing_connections(hub_slugs={"area-a", "area-b"}) == []


def test_detect_missing_connections_excludes_pairs_sharing_a_source(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    # Each page still qualifies with >=5 distinct sources, but one of those
    # sources ("raw/paper/shared.md") is the same file across every AreaA
    # and AreaB page, so every cross pair shares a source.
    for i in range(5):
        for j in range(4):
            create_or_update_page("concept", f"Shared A {i}", date(2026, 8, 4),
                                   source_path=f"raw/paper/shared-a-{i}-{j}.md", wikilinks=["area-a"], summary="x")
        create_or_update_page("concept", f"Shared A {i}", date(2026, 8, 4),
                               source_path="raw/paper/shared.md", wikilinks=["area-a"], summary="x")
    for i in range(5):
        for j in range(4):
            create_or_update_page("concept", f"Shared B {i}", date(2026, 8, 4),
                                   source_path=f"raw/paper/shared-b-{i}-{j}.md", wikilinks=["area-b"], summary="x")
        create_or_update_page("concept", f"Shared B {i}", date(2026, 8, 4),
                               source_path="raw/paper/shared.md", wikilinks=["area-b"], summary="x")

    candidates = detect_missing_connections(hub_slugs={"area-a", "area-b"})
    assert candidates == []


def test_detect_missing_connections_never_pairs_a_page_with_itself(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    # A page that has accumulated wikilinks to *both* hubs (e.g. via repeated
    # canonical updates over time) must never be paired against itself, and
    # run_and_create_comparisons must not crash indexing into its sources.
    create_or_update_page("concept", "Multi Hub Problem", date(2026, 8, 4),
                           source_path="raw/paper/multi-0.md", wikilinks=["area-a", "area-b"], summary="x")
    for j in range(1, 5):
        create_or_update_page("concept", "Multi Hub Problem", date(2026, 8, 4),
                               source_path=f"raw/paper/multi-{j}.md", wikilinks=[], summary="x")
    _make_area("Other", 1, "area-a")

    candidates = detect_missing_connections(hub_slugs={"area-a", "area-b"})
    assert all(c["page_a"] != c["page_b"] for c in candidates)
    # Must not raise (e.g. IndexError on an empty sources list).
    run_and_create_comparisons(date(2026, 8, 4), hub_slugs={"area-a", "area-b"})


def test_run_and_create_comparisons_creates_pages_and_skips_existing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    _make_area("AreaA", 5, "area-a")
    _make_area("AreaB", 5, "area-b")

    # 25 candidate pairs exist, but one run creates at most
    # MAX_NEW_COMPARISONS_PER_RUN pages (Finding C1); the rest are picked up
    # by later runs, which is why the second run below is non-empty.
    created_first = run_and_create_comparisons(date(2026, 8, 4), hub_slugs={"area-a", "area-b"})
    assert len(created_first) == MAX_NEW_COMPARISONS_PER_RUN
    for slug in created_first:
        assert (tmp_path / "comparisons" / f"{slug}.md").exists()

    created_second = run_and_create_comparisons(date(2026, 8, 7), hub_slugs={"area-a", "area-b"})
    assert set(created_second).isdisjoint(created_first)  # never re-creates an existing comparison


def test_run_and_create_comparisons_stores_the_full_evidence_not_just_one_source(tmp_path, monkeypatch):
    """A comparison page used to store exactly one of the (often 10+)
    sources that actually justified the pairing — understating how
    well-evidenced the flagged gap really is, and (since confidence was
    always "medium" on creation, regardless of source count) making an
    obviously well-supported gap look weakly-evidenced."""
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    _make_area("AreaA", 1, "area-a", sources_per_page=7)
    _make_area("AreaB", 1, "area-b", sources_per_page=6)

    created = run_and_create_comparisons(date(2026, 8, 16), hub_slugs={"area-a", "area-b"})
    assert len(created) == 1

    fm, _ = read_page("comparison", "AreaA Problem 0 vs AreaB Problem 0: underexplored connection")
    assert len(fm["sources"]) == 13  # 7 + 6, not 1
    assert fm["confidence"] == "high"


def test_run_and_create_comparisons_caps_new_pages_per_run(tmp_path, monkeypatch):
    """Finding C1: comparison creation scans the whole accumulated corpus
    every run, so without a cap one run can create O(n^2) pages (empirically
    190 from 20 qualifying pages). Cap new-page creation per run."""
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    _make_area("AreaA", 5, "area-a")   # 5 x 5 = 25 disjoint qualifying pairs,
    _make_area("AreaB", 5, "area-b")   # well above MAX_NEW_COMPARISONS_PER_RUN

    assert len(detect_missing_connections(hub_slugs={"area-a", "area-b"})) > MAX_NEW_COMPARISONS_PER_RUN

    created = run_and_create_comparisons(date(2026, 8, 4), hub_slugs={"area-a", "area-b"})
    assert len(created) == MAX_NEW_COMPARISONS_PER_RUN
    assert len(list((tmp_path / "comparisons").glob("*.md"))) == MAX_NEW_COMPARISONS_PER_RUN


def test_run_and_create_comparisons_prefers_highest_evidence_candidates(tmp_path, monkeypatch):
    """Finding C1: the per-run budget must go to the most-supported gaps,
    not to arbitrary filesystem-order ones."""
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    # Low-evidence area: exactly the 5-source minimum on every page.
    _make_area("AreaA", 6, "area-a", sources_per_page=5)
    _make_area("AreaB", 6, "area-b", sources_per_page=5)
    # One high-evidence page on each side (12 sources each): every pair
    # involving them outranks the 5+5=10-source baseline pairs.
    _make_area("Rich", 1, "area-a", sources_per_page=12)
    _make_area("Wealthy", 1, "area-b", sources_per_page=12)

    created = run_and_create_comparisons(date(2026, 8, 4), hub_slugs={"area-a", "area-b"})
    assert len(created) == MAX_NEW_COMPARISONS_PER_RUN
    # The single richest pair (12 + 12 sources) must be in the budget.
    assert "rich-problem-0-vs-wealthy-problem-0-underexplored-connection" in created
    # Every created page must involve at least one high-evidence page —
    # baseline-vs-baseline pairs (10 sources) all rank below the
    # 12+5=17-source mixed pairs, of which there are more than the budget.
    assert all("rich-problem-0" in slug or "wealthy-problem-0" in slug for slug in created)


def test_research_gap_pages_order_is_independent_of_filesystem_order(tmp_path, monkeypatch):
    """Finding I3: directory.glob() returns filesystem order, so the same
    underlying pair could yield 'A vs B' one run and 'B vs A' the next — a
    different title the dedup check can't match, creating a near-duplicate."""
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    # Create in deliberately reverse-alphabetical order.
    _make_area("Zzz", 1, "area-b")
    _make_area("Aaa", 1, "area-a")

    slugs = [p["slug"] for p in _research_gap_pages()]
    assert slugs == sorted(slugs)

    candidates = detect_missing_connections(hub_slugs={"area-a", "area-b"})
    assert len(candidates) == 1
    # Deterministic sorted-by-slug order, not creation order.
    assert candidates[0]["page_a"] == "Aaa Problem 0"
    assert candidates[0]["page_b"] == "Zzz Problem 0"


def test_run_and_create_comparisons_skips_malformed_existing_comparison(tmp_path, monkeypatch):
    """Re-review Minor 2: the read_page dedup check was unguarded, so one
    malformed pre-existing comparisons/ file raised out of the whole loop
    and cost every other candidate its creation for that run."""
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    _make_area("AreaA", 2, "area-a")
    _make_area("AreaB", 2, "area-b")

    candidates = detect_missing_connections(hub_slugs={"area-a", "area-b"})
    assert len(candidates) == 4
    # Hand-write one of the four expected comparison pages in unsupported
    # block-style YAML, so read_page raises for that candidate only.
    bad = candidates[0]
    bad_title = f"{bad['page_a']} vs {bad['page_b']}: underexplored connection"
    bad_path = tmp_path / "comparisons" / f"{slugify(bad_title)}.md"
    bad_path.parent.mkdir(parents=True, exist_ok=True)
    bad_path.write_text(
        '---\ntitle: "Broken"\ntype: "comparison"\ntags:\n  - research\n---\n\n# Broken\n',
        encoding="utf-8",
    )

    created = run_and_create_comparisons(date(2026, 8, 4), hub_slugs={"area-a", "area-b"})

    assert len(created) == 3  # the other three candidates were still created
    assert slugify(bad_title) not in created
    for slug in created:
        assert (tmp_path / "comparisons" / f"{slug}.md").exists()
    # The malformed page was never overwritten.
    assert "- research\n" in bad_path.read_text(encoding="utf-8")


def test_research_gap_pages_skips_malformed_page_without_aborting_the_run(tmp_path, monkeypatch):
    """Finding I5 part B: one malformed (hand-edited block-YAML) page must
    not raise out of gap detection and block every other valid page."""
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    _make_area("AreaA", 1, "area-a")
    _make_area("AreaB", 1, "area-b")

    (tmp_path / "concepts" / "hand-edited.md").write_text(
        '---\ntitle: "Hand Edited"\ntype: concept\ntags:\n  - research\n  - research-gap\n'
        'sources:\n  - raw/paper/a.md\n---\n\n# Hand Edited\n',
        encoding="utf-8",
    )

    slugs = [p["slug"] for p in _research_gap_pages()]
    assert "hand-edited" not in slugs
    assert {"areaa-problem-0", "areab-problem-0"} <= set(slugs)

    candidates = detect_missing_connections(hub_slugs={"area-a", "area-b"})
    assert len(candidates) == 1
    assert {candidates[0]["page_a"], candidates[0]["page_b"]} == {"AreaA Problem 0", "AreaB Problem 0"}


def test_run_and_create_comparisons_skips_already_done_and_links_pages(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    _make_area("AreaA", 1, "area-a")
    _make_area("AreaB", 1, "area-b")
    monkeypatch.setattr(
        "src.wiki_gap_detector.validate_gap_pair",
        lambda a, b: {"verdict": "already_done", "hits": [{"title": "Joint"}] * 5, "count": 5},
    )

    created = run_and_create_comparisons(date(2026, 9, 23), hub_slugs={"area-a", "area-b"})
    assert created == []
    assert list((tmp_path / "comparisons").glob("*.md")) == []
    _, body_a = read_page("concept", "AreaA Problem 0")
    _, body_b = read_page("concept", "AreaB Problem 0")
    assert "[[areab-problem-0]]" in body_a
    assert "[[areaa-problem-0]]" in body_b


def test_run_and_create_comparisons_queues_needs_human_without_a_page(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    _make_area("AreaA", 1, "area-a")
    _make_area("AreaB", 1, "area-b")
    monkeypatch.setattr(
        "src.wiki_gap_detector.validate_gap_pair",
        lambda a, b: {"verdict": "needs_human", "hits": [], "count": 0},
    )

    created = run_and_create_comparisons(date(2026, 9, 23), hub_slugs={"area-a", "area-b"})
    assert created == []
    queued = json.loads((tmp_path / "research-gap" / "gap_needs_human.json").read_text(encoding="utf-8"))
    assert queued["candidates"][0]["page_a"] == "AreaA Problem 0"

