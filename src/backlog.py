"""Topic backlog queue for the research-gap daily pipeline."""
from __future__ import annotations

import json
import re
from pathlib import Path


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:80].strip("-") or "topic"


def load_backlog(path: Path) -> dict:
    if not path.exists():
        return {"topics": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_backlog(path: Path, backlog: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(backlog, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def pop_pending_topics(backlog: dict, n: int = 3) -> list[dict]:
    return [t for t in backlog["topics"] if t["status"] == "pending"][:n]


def mark_done(backlog: dict, topic_id: str) -> None:
    for topic in backlog["topics"]:
        if topic["id"] == topic_id:
            topic["status"] = "done"
            return


def add_curiosity_topics(
    backlog: dict, topic_strings: list[str], added_date: str, source: str = "curiosity"
) -> list[str]:
    existing_ids = {t["id"] for t in backlog["topics"]}
    existing_slugs = {slugify(t["topic"]) for t in backlog["topics"]}
    seen = existing_ids | existing_slugs
    new_entries = []
    added = []
    for topic in topic_strings:
        topic_id = slugify(topic)
        if topic_id in seen:
            continue
        seen.add(topic_id)
        new_entries.append({
            "id": topic_id, "topic": topic, "status": "pending",
            "source": source, "added_date": added_date,
        })
        added.append(topic)
    backlog["topics"] = new_entries + backlog["topics"]
    return added
