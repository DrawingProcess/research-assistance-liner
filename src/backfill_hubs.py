"""Backfill v2 hub sections from existing raw/paper records and local
synthesis JSON. Does not call Liner and does not rewrite raw bodies.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from src.backlog import load_backlog, slugify
from src.canonical_pages import parse_frontmatter
from src.hub import update_hub
from src.paper_identity import canonical_id, register

RAW_DIR = Path("raw/paper")
BACKLOG_PATH = Path("research-gap/backlog.json")
RUNS_DIR = Path("research-gap/runs")
IDENTITY_PATH = Path("research-gap/paper_identity.json")


def _section_bullets(body: str, heading: str) -> list[str]:
    lines = body.splitlines()
    key = f"## {heading}"
    if key not in lines:
        return []
    i = lines.index(key) + 1
    out = []
    while i < len(lines) and not lines[i].startswith("## "):
        if lines[i].startswith("- "):
            out.append(lines[i][2:].strip())
        i += 1
    return out


def parse_raw_paper(path: Path) -> dict | None:
    try:
        fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    rel = str(path) if path.as_posix().startswith("raw/") else f"raw/paper/{path.name}"
    return {
        "title": fm.get("title") or path.stem,
        "url": fm.get("url") or "",
        "path": rel,
        "liner_query": fm.get("liner_query") or "",
        "problem": _section_bullets(body, "Problem"),
        "method": _section_bullets(body, "Method"),
        "dataset": _section_bullets(body, "Dataset"),
        "task": _section_bullets(body, "Task"),
        "limitations": _section_bullets(body, "Limitations"),
    }


def papers_by_topic(raw_dir: Path = RAW_DIR) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    if not raw_dir.exists():
        return grouped
    for path in sorted(raw_dir.glob("*.md")):
        parsed = parse_raw_paper(path)
        if not parsed or not parsed["liner_query"]:
            continue
        grouped.setdefault(parsed["liner_query"], []).append(parsed)
    return grouped


def papers_for_topic(topic: str, raw_dir: Path = RAW_DIR) -> list[dict]:
    return papers_by_topic(raw_dir).get(topic, [])


def backfill_hub(topic: str, today: date, raw_dir: Path = RAW_DIR, runs_dir: Path = RUNS_DIR,
                 papers: list[dict] | None = None) -> dict:
    papers = papers if papers is not None else papers_for_topic(topic, raw_dir)
    themes: dict[str, list[str]] = {}
    challenges: list[str] = []
    for paper in papers:
        for label in paper["problem"] + paper["method"] + paper["dataset"] + paper["task"]:
            themes.setdefault(label, []).append(paper["path"])
        challenges.extend(paper["limitations"])
    update_hub(
        topic, today,
        sources=[p["path"] for p in papers],
        definition=load_local_definition(slugify(topic), runs_dir),
        challenges=challenges,
        papers=papers,
        themes=themes,
        adjacent=[],
        related=[],
    )
    return {"topic": topic, "papers": len(papers), "themes": len(themes)}


def backfill_all(today: date, backlog_path: Path = BACKLOG_PATH, raw_dir: Path = RAW_DIR) -> list[dict]:
    backlog = load_backlog(backlog_path)
    grouped = papers_by_topic(raw_dir)
    results = []
    for entry in backlog.get("topics", []):
        if entry.get("status") != "done":
            continue
        results.append(backfill_hub(entry["topic"], today, raw_dir=raw_dir,
                                    papers=grouped.get(entry["topic"], [])))
    return results


def load_local_definition(topic_id: str, runs_dir: Path = RUNS_DIR) -> str:
    if not runs_dir.exists():
        return ""
    matches = sorted(runs_dir.glob(f"*/{topic_id}_synthesis.json"))
    if not matches:
        return ""
    try:
        data = json.loads(matches[-1].read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return ""
    text = (data.get("search_agent_scholar") or {}).get("text") or ""
    return text[:800]


def register_raw_identities(raw_dir: Path = RAW_DIR, identity_path: Path = IDENTITY_PATH) -> int:
    if not raw_dir.exists():
        return 0
    n = 0
    for path in raw_dir.glob("*.md"):
        parsed = parse_raw_paper(path)
        if not parsed or not parsed["url"]:
            continue
        rel = parsed["path"]
        register(canonical_id(parsed["url"], parsed["title"]), rel, parsed["url"], path=identity_path)
        n += 1
    return n


def main() -> None:
    today = date.today()
    registered = register_raw_identities()
    results = backfill_all(today)
    print(f"registered {registered} identity keys; backfilled {len(results)} hubs")


if __name__ == "__main__":
    main()
