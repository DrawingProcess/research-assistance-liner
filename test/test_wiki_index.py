from datetime import date

from src.wiki_index import append_log, upsert_index_entry

INDEX_TEMPLATE = """# Wiki Index

> Complete catalog of active canonical pages. Each entry is a wikilink followed by
> a one-line summary, sorted alphabetically within its section.
>
> Total pages: 0

## Entities

## Concepts

## Comparisons

## Queries
"""


def test_upsert_index_entry_adds_new_entry_and_updates_total(tmp_path):
    index_path = tmp_path / "index.md"
    index_path.write_text(INDEX_TEMPLATE, encoding="utf-8")

    upsert_index_entry("concept", "world-model", "World Model", "Research hub for world model.", index_path=index_path)

    text = index_path.read_text(encoding="utf-8")
    assert "- [[world-model]] — Research hub for world model." in text
    assert "Total pages: 1" in text
    concepts_section = text.split("## Concepts")[1].split("## Comparisons")[0]
    assert "world-model" in concepts_section


def test_upsert_index_entry_sorts_alphabetically_within_section(tmp_path):
    index_path = tmp_path / "index.md"
    index_path.write_text(INDEX_TEMPLATE, encoding="utf-8")

    upsert_index_entry("concept", "zeta-topic", "Zeta Topic", "z", index_path=index_path)
    upsert_index_entry("concept", "alpha-topic", "Alpha Topic", "a", index_path=index_path)

    text = index_path.read_text(encoding="utf-8")
    concepts_section = text.split("## Concepts")[1].split("## Comparisons")[0]
    assert concepts_section.index("alpha-topic") < concepts_section.index("zeta-topic")


def test_upsert_index_entry_replaces_existing_entry_for_same_slug(tmp_path):
    index_path = tmp_path / "index.md"
    index_path.write_text(INDEX_TEMPLATE, encoding="utf-8")

    upsert_index_entry("concept", "world-model", "World Model", "old summary", index_path=index_path)
    upsert_index_entry("concept", "world-model", "World Model", "new summary", index_path=index_path)

    text = index_path.read_text(encoding="utf-8")
    assert text.count("[[world-model]]") == 1
    assert "new summary" in text
    assert "old summary" not in text
    assert "Total pages: 1" in text


def test_append_log_writes_expected_format(tmp_path):
    log_path = tmp_path / "log.md"
    log_path.write_text("# Wiki Log\n\n", encoding="utf-8")

    append_log("create", "World Model", ["concepts/world-model.md"], date(2026, 8, 4), log_path=log_path)

    text = log_path.read_text(encoding="utf-8")
    assert "## [2026-08-04] create | World Model" in text
    assert "- concepts/world-model.md" in text


def test_upsert_index_entry_summary_cannot_inject_a_heading(tmp_path):
    """Finding C2: a summary built from an externally-sourced label with an
    embedded newline must not break index.md's section structure."""
    index_path = tmp_path / "index.md"
    index_path.write_text(INDEX_TEMPLATE, encoding="utf-8")

    upsert_index_entry(
        "concept", "world-model", "World Model",
        "benign summary\n## Injected Section\n- [[fake-page]] — fake",
        index_path=index_path,
    )

    text = index_path.read_text(encoding="utf-8")
    # The injected text survives as inline text on the entry's own line
    # (harmless); what must never happen is it becoming a structural line.
    assert [line for line in text.splitlines() if line.startswith("## ")] == [
        "## Entities", "## Concepts", "## Comparisons", "## Queries",
    ]
    assert "- [[world-model]] — benign summary ## Injected Section - [[fake-page]] — fake" in text


def test_append_log_subject_cannot_inject_a_heading(tmp_path):
    """Finding C2: a paper title with an embedded newline must stay on its
    own single log heading line."""
    log_path = tmp_path / "log.md"
    log_path.write_text("# Wiki Log\n\n", encoding="utf-8")

    append_log("create", "Benign Title\n## [2026-01-01] delete | fake entry",
               ["concepts/x.md"], date(2026, 8, 4), log_path=log_path)

    text = log_path.read_text(encoding="utf-8")
    headings = [line for line in text.splitlines() if line.startswith("## ")]
    assert headings == ["## [2026-08-04] create | Benign Title ## [2026-01-01] delete | fake entry"]
