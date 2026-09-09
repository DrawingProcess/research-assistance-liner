import json
from datetime import date

from src.raw_paper import write_paper

STRUCTURED = {
    "problem": ["open-vocabulary understanding"],
    "method": ["semantic gaussian representation"],
    "dataset": ["ScanNet"],
    "task": [],
    "evaluation": [],
    "limitations": ["weak relational reasoning"],
    "future_work": [],
}
PAPER = {
    "title": "Semantic Gaussians", "url": "https://arxiv.org/abs/1234",
    "date": "2024-03-22", "journal": "CVPR 2024", "authors": ["A. One", "B. Two"],
    "description": "We propose a method for open-vocabulary scene understanding.",
}


def test_write_paper_creates_frontmatter_and_body(tmp_path):
    raw_dir = tmp_path / "raw" / "paper"
    path, is_new = write_paper(PAPER, STRUCTURED, "3DGS scene graph", date(2026, 8, 4), raw_dir=raw_dir)

    assert is_new is True
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert 'title: "Semantic Gaussians"' in text
    assert 'url: "https://arxiv.org/abs/1234"' in text  # json.dumps-escaped now (Minor 3)
    assert 'published: "2024-03-22"' in text
    assert 'venue: "CVPR 2024"' in text  # json.dumps-escaped now (C2)
    assert 'liner_query: "3DGS scene graph"' in text
    assert "ingested: 2026-08-04" in text
    assert "type: paper" in text
    assert '"research"' in text and '"research-gap"' in text
    assert "## Abstract" in text
    assert "We propose a method" in text
    assert "## Method" in text
    assert "- semantic gaussian representation" in text
    assert "## Limitations" in text


def test_write_paper_computes_sha256_over_body_only(tmp_path):
    raw_dir = tmp_path / "raw" / "paper"
    path, _ = write_paper(PAPER, STRUCTURED, "3DGS scene graph", date(2026, 8, 4), raw_dir=raw_dir)
    text = path.read_text(encoding="utf-8")

    import hashlib
    frontmatter_end = text.index("\n---\n", 4) + len("\n---\n")
    body = text[frontmatter_end:]
    expected_sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
    assert f"sha256: {expected_sha}" in text


def test_write_paper_dedupes_by_url(tmp_path):
    raw_dir = tmp_path / "raw" / "paper"
    path1, is_new1 = write_paper(PAPER, STRUCTURED, "3DGS scene graph", date(2026, 8, 4), raw_dir=raw_dir)
    path2, is_new2 = write_paper(PAPER, STRUCTURED, "different topic", date(2026, 8, 5), raw_dir=raw_dir)

    assert is_new1 is True
    assert is_new2 is False
    assert path1 == path2
    assert len(list(raw_dir.glob("*.md"))) == 1


def test_write_paper_dedupes_arxiv_papers_across_url_and_doi_form(tmp_path):
    """Liner Scholar Search sometimes returns the identical arXiv paper
    under two different URL forms across separate calls — arxiv.org/abs/
    <id> vs doi.org/10.48550/arxiv.<id>, arXiv's own DOI prefix for the
    same paper — which used to defeat exact-string dedup and create a
    duplicate raw/paper/ record (observed live: ~30 pairs in the real
    corpus, e.g. https://arxiv.org/abs/2606.01869 and
    https://doi.org/10.48550/arxiv.2606.01869)."""
    raw_dir = tmp_path / "raw" / "paper"
    paper_arxiv_form = {**PAPER, "url": "https://arxiv.org/abs/2606.01869"}
    paper_doi_form = {**PAPER, "url": "https://doi.org/10.48550/arxiv.2606.01869"}

    path1, is_new1 = write_paper(paper_arxiv_form, STRUCTURED, "t", date(2026, 8, 4), raw_dir=raw_dir)
    path2, is_new2 = write_paper(paper_doi_form, STRUCTURED, "t", date(2026, 8, 5), raw_dir=raw_dir)

    assert is_new1 is True
    assert is_new2 is False
    assert path1 == path2
    assert len(list(raw_dir.glob("*.md"))) == 1
    # The originally-captured URL form is preserved verbatim, not rewritten.
    assert 'url: "https://arxiv.org/abs/2606.01869"' in path1.read_text(encoding="utf-8")


def test_write_paper_dedupes_arxiv_papers_ignoring_version_suffix(tmp_path):
    raw_dir = tmp_path / "raw" / "paper"
    v1 = {**PAPER, "url": "https://arxiv.org/abs/2606.01869v1"}
    v2 = {**PAPER, "url": "https://arxiv.org/abs/2606.01869v2"}

    _, is_new1 = write_paper(v1, STRUCTURED, "t", date(2026, 8, 4), raw_dir=raw_dir)
    _, is_new2 = write_paper(v2, STRUCTURED, "t", date(2026, 8, 5), raw_dir=raw_dir)

    assert is_new1 is True
    assert is_new2 is False


def test_write_paper_does_not_conflate_different_arxiv_papers(tmp_path):
    raw_dir = tmp_path / "raw" / "paper"
    paper_a = {**PAPER, "url": "https://arxiv.org/abs/2606.01869"}
    paper_b = {**PAPER, "url": "https://arxiv.org/abs/2606.01870"}  # different id, one digit off

    _, is_new_a = write_paper(paper_a, STRUCTURED, "t", date(2026, 8, 4), raw_dir=raw_dir)
    _, is_new_b = write_paper(paper_b, STRUCTURED, "t", date(2026, 8, 5), raw_dir=raw_dir)

    assert is_new_a is True
    assert is_new_b is True
    assert len(list(raw_dir.glob("*.md"))) == 2


def test_write_paper_still_dedupes_non_arxiv_urls_by_exact_match(tmp_path):
    raw_dir = tmp_path / "raw" / "paper"
    paper = {**PAPER, "url": "https://openreview.net/forum?id=abc123"}

    _, is_new1 = write_paper(paper, STRUCTURED, "t", date(2026, 8, 4), raw_dir=raw_dir)
    _, is_new2 = write_paper(paper, STRUCTURED, "t", date(2026, 8, 5), raw_dir=raw_dir)

    assert is_new1 is True
    assert is_new2 is False


def test_write_paper_escapes_quotes_in_title_and_query(tmp_path):
    """Finding C2: a paper title containing a literal `"` used to produce
    invalid, unparseable frontmatter in an *immutable* raw/paper/ record."""
    raw_dir = tmp_path / "raw" / "paper"
    paper = dict(PAPER, title='Semantic "Gaussian" Splatting for 3D',
                 url="https://arxiv.org/abs/5555", journal='The "Best" Journal')
    path, _ = write_paper(paper, STRUCTURED, 'query with "quotes"', date(2026, 8, 4), raw_dir=raw_dir)

    text = path.read_text(encoding="utf-8")
    fm_text = text[: text.index("\n---\n", 4)]
    parsed = {
        line.split(":", 1)[0]: json.loads(line.split(":", 1)[1].strip())
        for line in fm_text.splitlines()
        if line.split(":", 1)[0] in ("title", "venue", "liner_query")
    }
    assert parsed["title"] == 'Semantic "Gaussian" Splatting for 3D'
    assert parsed["venue"] == 'The "Best" Journal'
    assert parsed["liner_query"] == 'query with "quotes"'


def test_write_paper_escapes_url_and_published_and_still_dedupes(tmp_path):
    """Re-review Minor 3: url/published were interpolated raw. An odd
    character in either broke the frontmatter line — and for `url` it also
    broke _url_index's own parsing of `url:` back out, which is what dedup
    depends on."""
    raw_dir = tmp_path / "raw" / "paper"
    weird_url = 'https://example.org/a"b?q=1'
    paper = dict(PAPER, title="Odd URL Paper", url=weird_url, date='2024-01-01 "approx"')

    path, is_new = write_paper(paper, STRUCTURED, "topic", date(2026, 8, 4), raw_dir=raw_dir)
    assert is_new is True

    text = path.read_text(encoding="utf-8")
    fm_text = text[: text.index("\n---\n", 4)]
    parsed = {
        line.split(":", 1)[0]: json.loads(line.split(":", 1)[1].strip())
        for line in fm_text.splitlines()
        if line.split(":", 1)[0] in ("url", "published")
    }
    assert parsed["url"] == weird_url
    assert parsed["published"] == '2024-01-01 "approx"'

    # Dedup still recognises the record through the escaped url line.
    path2, is_new2 = write_paper(paper, STRUCTURED, "topic", date(2026, 8, 7), raw_dir=raw_dir)
    assert (path2, is_new2) == (path, False)


def test_url_index_still_dedupes_legacy_unescaped_url_records(tmp_path):
    """raw/paper/ records are immutable, so records written before Minor 3
    still carry a bare `url:` line — dedup must keep recognising them or the
    pipeline would re-capture (and re-pay for) every pre-existing paper."""
    raw_dir = tmp_path / "raw" / "paper"
    raw_dir.mkdir(parents=True)
    (raw_dir / "legacy.md").write_text(
        '---\ntitle: "Legacy"\nurl: https://arxiv.org/abs/1234\n---\n\n## Abstract\n\nx\n',
        encoding="utf-8",
    )

    path, is_new = write_paper(PAPER, STRUCTURED, "topic", date(2026, 8, 4), raw_dir=raw_dir)
    assert is_new is False
    assert path == raw_dir / "legacy.md"


def test_write_paper_logs_ingest_once_per_new_record(tmp_path, monkeypatch):
    """Finding M2: raw/paper captures are a wiki write like any other and
    must leave an `ingest` audit trail — but a dedup hit must not re-log."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "log.md").write_text("# Wiki Log\n\n", encoding="utf-8")
    raw_dir = tmp_path / "raw" / "paper"

    write_paper(PAPER, STRUCTURED, "3DGS scene graph", date(2026, 8, 4), raw_dir=raw_dir)
    text = (tmp_path / "log.md").read_text(encoding="utf-8")
    assert "## [2026-08-04] ingest | Semantic Gaussians" in text
    assert text.count("ingest | Semantic Gaussians") == 1
    assert "- " + str(raw_dir / "semantic-gaussians.md") in text

    # Same URL again: dedup hit, no second log entry.
    write_paper(PAPER, STRUCTURED, "other topic", date(2026, 8, 7), raw_dir=raw_dir)
    text = (tmp_path / "log.md").read_text(encoding="utf-8")
    assert text.count("ingest | Semantic Gaussians") == 1


def test_write_paper_log_entry_cannot_inject_a_heading(tmp_path, monkeypatch):
    """Finding C2 + M2: a title with an embedded newline reaching log.md via
    the ingest entry must not inject a fake log heading."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "log.md").write_text("# Wiki Log\n\n", encoding="utf-8")
    raw_dir = tmp_path / "raw" / "paper"
    paper = dict(PAPER, title="Benign\n## [2026-01-01] delete | fake", url="https://arxiv.org/abs/777")

    write_paper(paper, STRUCTURED, "topic", date(2026, 8, 4), raw_dir=raw_dir)

    text = (tmp_path / "log.md").read_text(encoding="utf-8")
    headings = [line for line in text.splitlines() if line.startswith("## ")]
    assert headings == ["## [2026-08-04] ingest | Benign ## [2026-01-01] delete | fake"]


def test_write_paper_handles_missing_optional_fields(tmp_path):
    raw_dir = tmp_path / "raw" / "paper"
    sparse_paper = {"title": "Sparse Paper", "url": "https://arxiv.org/abs/9999", "date": "2024-01-01"}
    path, is_new = write_paper(sparse_paper, STRUCTURED, "topic", date(2026, 8, 4), raw_dir=raw_dir)
    assert is_new is True
    text = path.read_text(encoding="utf-8")
    assert "venue: null" in text
    assert "authors: []" in text
