# test/test_canonical_pages.py
from datetime import date

import pytest

from src.canonical_pages import CANONICAL_DIRS, create_or_update_page, page_path, parse_frontmatter, read_page

_INDEX_TEMPLATE = """# Wiki Index

> Total pages: 0

## Entities

## Concepts

## Comparisons

## Queries
"""


def _seed_wiki_files(tmp_path):
    (tmp_path / "index.md").write_text(_INDEX_TEMPLATE, encoding="utf-8")
    (tmp_path / "log.md").write_text("# Wiki Log\n\n", encoding="utf-8")


def test_page_path_uses_slug_under_correct_directory():
    assert page_path("entity", "ScanNet") == CANONICAL_DIRS["entity"] / "scannet.md"
    assert page_path("concept", "World Model") == CANONICAL_DIRS["concept"] / "world-model.md"


def test_create_or_update_page_creates_new_page(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_wiki_files(tmp_path)

    action = create_or_update_page(
        "entity", "ScanNet", date(2026, 8, 4), source_path="raw/paper/a.md",
        wikilinks=["world-model", "3d-scene-understanding"], summary="A dataset used across papers.",
    )
    assert action == "create"

    path = CANONICAL_DIRS["entity"] / "scannet.md"
    text = path.read_text(encoding="utf-8")
    assert 'title: "ScanNet"' in text
    # Every string scalar is json.dumps-encoded now, including `type` (C2).
    assert 'type: "entity"' in text
    assert '"raw/paper/a.md"' in text
    assert "[[world-model]]" in text
    assert "[[3d-scene-understanding]]" in text


def test_create_or_update_page_second_call_updates_sources_and_confidence(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_wiki_files(tmp_path)
    create_or_update_page("entity", "ScanNet", date(2026, 8, 4), source_path="raw/paper/a.md",
                           wikilinks=["world-model"], summary="A dataset used across papers.")

    action = create_or_update_page("entity", "ScanNet", date(2026, 8, 5), source_path="raw/paper/b.md",
                                    wikilinks=["world-model"], summary="A dataset used across papers.")
    assert action == "update"

    fm, _ = read_page("entity", "ScanNet")
    assert fm["sources"] == ["raw/paper/a.md", "raw/paper/b.md"]
    assert fm["confidence"] == "high"
    assert fm["updated"] == "2026-08-05"
    assert fm["created"] == "2026-08-04"


def test_create_or_update_page_accepts_a_list_of_sources_on_creation(tmp_path, monkeypatch):
    """A gap candidate's whole evidence base is known up front — it
    shouldn't have to call this once per source just to accumulate them
    (that used to mean N file rewrites, N index.md updates, and N
    near-identical log.md entries for one creation event, and previously
    only the first source ever got stored at all)."""
    monkeypatch.chdir(tmp_path)
    _seed_wiki_files(tmp_path)

    action = create_or_update_page(
        "comparison", "A vs B: underexplored connection", date(2026, 8, 16),
        source_path=["raw/paper/a.md", "raw/paper/b.md", "raw/paper/c.md"],
        wikilinks=["a", "b"], summary="x",
    )
    assert action == "create"

    fm, _ = read_page("comparison", "A vs B: underexplored connection")
    assert fm["sources"] == ["raw/paper/a.md", "raw/paper/b.md", "raw/paper/c.md"]
    # >=2 sources on creation must start at "high", not wait for a later
    # update that, for auto-created comparison pages, never actually comes
    # (they're only ever created once — see run_and_create_comparisons'
    # dedup-by-existence check).
    assert fm["confidence"] == "high"


def test_create_or_update_page_dedupes_within_a_list_of_sources(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_wiki_files(tmp_path)

    create_or_update_page(
        "comparison", "A vs B: underexplored connection", date(2026, 8, 16),
        source_path=["raw/paper/a.md", "raw/paper/a.md", "raw/paper/b.md"],
        wikilinks=["a", "b"], summary="x",
    )
    fm, _ = read_page("comparison", "A vs B: underexplored connection")
    assert fm["sources"] == ["raw/paper/a.md", "raw/paper/b.md"]


def test_create_or_update_page_list_source_still_appends_to_existing_on_update(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_wiki_files(tmp_path)
    create_or_update_page("entity", "ScanNet", date(2026, 8, 4), source_path="raw/paper/a.md",
                           wikilinks=["world-model"], summary="x")

    action = create_or_update_page(
        "entity", "ScanNet", date(2026, 8, 5), source_path=["raw/paper/a.md", "raw/paper/b.md"],
        wikilinks=["world-model"], summary="x",
    )
    assert action == "update"
    fm, _ = read_page("entity", "ScanNet")
    assert fm["sources"] == ["raw/paper/a.md", "raw/paper/b.md"]


def test_create_or_update_page_does_not_duplicate_same_source_or_wikilink(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_wiki_files(tmp_path)
    create_or_update_page("entity", "ScanNet", date(2026, 8, 4), source_path="raw/paper/a.md",
                           wikilinks=["world-model"], summary="A dataset used across papers.")

    create_or_update_page("entity", "ScanNet", date(2026, 8, 5), source_path="raw/paper/a.md",
                           wikilinks=["world-model"], summary="A dataset used across papers.")
    fm, body = read_page("entity", "ScanNet")
    assert fm["sources"] == ["raw/paper/a.md"]
    assert body.count("[[world-model]]") == 1


def test_create_or_update_page_folds_body_section_and_dedupes_bullets(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_wiki_files(tmp_path)

    create_or_update_page(
        "concept", "Open-Vocabulary Understanding", date(2026, 8, 4), source_path="raw/paper/a.md",
        wikilinks=["world-model"], summary="A recurring problem.",
        body_section=("Open challenges", "Weak relational reasoning"),
    )
    create_or_update_page(
        "concept", "Open-Vocabulary Understanding", date(2026, 8, 5), source_path="raw/paper/b.md",
        wikilinks=["world-model"], summary="A recurring problem.",
        body_section=("Open challenges", "Weak relational reasoning"),
    )

    _, body = read_page("concept", "Open-Vocabulary Understanding")
    assert body.count("Weak relational reasoning") == 1
    assert "## Open challenges" in body


def test_parse_frontmatter_roundtrips_with_create_or_update_page(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_wiki_files(tmp_path)
    create_or_update_page("entity", "ScanNet", date(2026, 8, 4), source_path="raw/paper/a.md",
                           wikilinks=["world-model"], summary="x")
    path = CANONICAL_DIRS["entity"] / "scannet.md"
    fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    assert fm["title"] == "ScanNet"
    assert fm["tags"] == ["research", "research-gap"]
    assert isinstance(body, str)


def test_read_page_returns_none_when_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert read_page("entity", "Nonexistent") is None


def test_title_with_embedded_quote_roundtrips_exactly(tmp_path, monkeypatch):
    """Finding C2: a label containing a literal `"` used to produce invalid,
    unparseable frontmatter. json.dumps/json.loads must round-trip it."""
    monkeypatch.chdir(tmp_path)
    _seed_wiki_files(tmp_path)
    title = 'Semantic "Gaussian" Splatting for 3D'

    create_or_update_page("entity", title, date(2026, 8, 4), source_path="raw/paper/a.md",
                           wikilinks=["world-model"], summary="x")

    fm, _ = read_page("entity", title)
    assert fm["title"] == title
    assert fm["tags"] == ["research", "research-gap"]
    assert fm["sources"] == ["raw/paper/a.md"]
    assert fm["contested"] is False


def test_label_with_embedded_newline_cannot_inject_a_heading(tmp_path, monkeypatch):
    """Finding C2: a Liner-extracted label containing '\\n## Injected' must
    not create a new markdown heading in the page body or the frontmatter."""
    monkeypatch.chdir(tmp_path)
    _seed_wiki_files(tmp_path)
    title = "Benign Label\n## Injected Heading"

    create_or_update_page("entity", title, date(2026, 8, 4), source_path="raw/paper/a.md",
                           wikilinks=["world-model"], summary="x",
                           body_section=("Open challenges", "bullet text\n## Injected Bullet Heading"))

    text = page_path("entity", title).read_text(encoding="utf-8")
    injected = [line for line in text.splitlines() if line.startswith("## Injected")]
    assert injected == []
    # The heading line is collapsed to one line; frontmatter keeps the exact
    # original string via the \n escape, so it still round-trips.
    assert "# Benign Label ## Injected Heading" in text
    fm, _ = read_page("entity", title)
    assert fm["title"] == title


def test_parse_frontmatter_rejects_block_style_yaml_tags(tmp_path, monkeypatch):
    """Finding I5: block-style YAML used to parse tags as an empty string,
    and the next create_or_update_page silently destroyed the research-gap
    tag — dropping the page out of gap detection forever, with no error."""
    monkeypatch.chdir(tmp_path)
    _seed_wiki_files(tmp_path)
    path = CANONICAL_DIRS["entity"] / "hand-edited.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '---\ntitle: "Hand Edited"\ncreated: "2026-08-01"\nupdated: "2026-08-01"\n'
        'type: "entity"\ntags:\n  - research\n  - research-gap\n'
        'sources: ["raw/paper/a.md"]\nconfidence: "medium"\ncontested: false\n'
        'contradictions: []\n---\n\n# Hand Edited\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="tags"):
        read_page("entity", "Hand Edited")
    with pytest.raises(ValueError, match="tags"):
        create_or_update_page("entity", "Hand Edited", date(2026, 8, 4), source_path="raw/paper/b.md",
                               wikilinks=["world-model"], summary="x")

    # The page on disk is untouched — its research-gap tag survives.
    assert "- research-gap" in path.read_text(encoding="utf-8")


def test_create_or_update_page_dedupes_duplicate_wikilinks_on_creation(tmp_path, monkeypatch):
    """Re-review Minor 1: _render_body didn't dedupe (only _merge_body did),
    so a wikilinks list containing the same slug twice produced two
    identical `- [[slug]]` lines on a newly created page."""
    monkeypatch.chdir(tmp_path)
    _seed_wiki_files(tmp_path)

    create_or_update_page("entity", "ScanNet", date(2026, 8, 4), source_path="raw/paper/a.md",
                           wikilinks=["world-model", "scannet-baseline", "world-model"], summary="x")

    _, body = read_page("entity", "ScanNet")
    assert body.count("- [[world-model]]") == 1
    assert body.count("- [[scannet-baseline]]") == 1


def test_parse_frontmatter_rejects_non_boolean_contested(tmp_path, monkeypatch):
    """Finding I5: `contested` must be a YAML boolean per SCHEMA.md."""
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="contested"):
        parse_frontmatter(
            '---\ntitle: "X"\ntags: ["research"]\ncontested: yes\n---\n\n# X\n'
        )
