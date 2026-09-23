"""Writes immutable raw/paper/ records for captured Liner Scholar Search
papers, per SCHEMA.md's raw/paper/ frontmatter (added in Task 1 of this
plan). Mechanical capture only — every value traces to one Liner response
about this one paper, nothing synthesized across sources.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path

from src.backlog import slugify
from src.wiki_index import append_log

RAW_PAPER_DIR = Path("raw/paper")

FIELD_HEADINGS = {
    "problem": "Problem", "method": "Method", "dataset": "Dataset",
    "task": "Task", "evaluation": "Evaluation", "limitations": "Limitations",
    "future_work": "Future Work",
}

_ARXIV_ID_RE = re.compile(r"(\d{4}\.\d{4,5})(?:v\d+)?")


def _canonical_url(url: str) -> str:
    """Liner Scholar Search sometimes returns the identical arXiv paper
    under two different URL forms across separate calls — arxiv.org/abs/<id>
    vs doi.org/10.48550/arxiv.<id> (arXiv's own DOI prefix for the same
    paper) — which defeats exact-string dedup and produces a duplicate
    raw/paper/ record (observed live: ~30 pairs in the corpus, e.g.
    https://arxiv.org/abs/2606.01869 and
    https://doi.org/10.48550/arxiv.2606.01869 are the same paper). Normalize
    both forms to the same key, stripping any version suffix (v1/v2/... of
    the same paper is still the same paper). Anything else falls back to
    the exact URL, unchanged."""
    lowered = url.lower()
    if "arxiv.org/abs/" in lowered or "doi.org/10.48550/arxiv." in lowered:
        match = _ARXIV_ID_RE.search(url)
        if match:
            return f"arxiv:{match.group(1)}"
    return url


def _url_index(raw_dir: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    if not raw_dir.exists():
        return index
    for md_file in raw_dir.glob("*.md"):
        text = md_file.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            if line.startswith("url:"):
                value = line.split("url:", 1)[1].strip()
                # `url` is json.dumps-encoded now (re-review, Minor 3), but
                # raw/paper/ records are immutable — any record written
                # before that change still has a bare URL here, and dedup
                # must keep recognising it or the pipeline would re-capture
                # and re-pay for every pre-existing paper.
                if value.startswith('"'):
                    try:
                        value = json.loads(value)
                    except ValueError:
                        pass
                index[_canonical_url(value)] = md_file
                break
    return index


def _build_body(abstract: str, structured: dict) -> str:
    lines = ["## Abstract", "", (abstract or "").strip(), ""]
    for field, heading in FIELD_HEADINGS.items():
        values = structured.get(field) or []
        if not values:
            continue
        lines += [f"## {heading}", ""]
        lines += [f"- {v}" for v in values]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_paper(
    paper: dict, structured: dict, topic: str, today: date, raw_dir: Path = RAW_PAPER_DIR
) -> tuple[Path, bool]:
    from src.paper_identity import lookup_path
    existing = lookup_path(paper["url"], paper.get("title") or "", raw_dir)
    if existing is not None:
        return existing, False
    existing = _url_index(raw_dir).get(_canonical_url(paper["url"]))
    if existing is not None:
        return existing, False

    body = _build_body(paper.get("description", ""), structured)
    sha256 = hashlib.sha256(body.encode("utf-8")).hexdigest()

    # Every externally-sourced string scalar is json.dumps-escaped: a title
    # containing a literal `"` would otherwise produce permanently invalid
    # frontmatter in an *immutable* raw/paper/ record, which SCHEMA.md's two
    # narrow raw-record mutations can't repair (Final review, Finding C2).
    frontmatter = "\n".join([
        "---",
        f"title: {json.dumps(paper['title'])}",
        f"authors: {json.dumps(paper.get('authors') or [])}",
        f"url: {json.dumps(paper['url'])}",
        f"published: {json.dumps(paper.get('date', ''))}",
        f"venue: {json.dumps(paper.get('journal')) if paper.get('journal') else 'null'}",
        f"liner_query: {json.dumps(topic)}",
        f"ingested: {today.isoformat()}",
        f"sha256: {sha256}",
        "type: paper",
        'tags: ["research", "research-gap"]',
        "---",
        "",
    ])
    content = frontmatter + body

    raw_dir.mkdir(parents=True, exist_ok=True)
    slug = slugify(paper["title"])
    path = raw_dir / f"{slug}.md"
    n = 2
    while path.exists():
        path = raw_dir / f"{slug}-{n}.md"
        n += 1
    path.write_text(content, encoding="utf-8")
    from src.paper_identity import canonical_id, register
    register(canonical_id(paper["url"], paper.get("title") or ""), str(path), paper["url"])
    append_log("ingest", paper["title"], [str(path)], today)
    return path, True
