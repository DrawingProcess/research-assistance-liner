"""index.md / log.md synchronization, per SCHEMA.md's "Index and log
synchronization" rule: every canonical create/update must update both in
the same operation.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

INDEX_PATH = Path("index.md")
LOG_PATH = Path("log.md")

SECTION_HEADINGS = {
    "entity": "## Entities", "concept": "## Concepts",
    "comparison": "## Comparisons", "query": "## Queries",
}


def _clean_line(text: str) -> str:
    """Collapse embedded newlines/control chars so externally-sourced text
    (a Liner-extracted label, a paper title) can never break out of its
    single index.md/log.md line and inject a `## heading` that permanently
    corrupts the file's section structure (Final review, Finding C2)."""
    return " ".join(text.split())


def upsert_index_entry(
    page_type: str, slug: str, title: str, summary: str, index_path: Path = INDEX_PATH
) -> None:
    text = index_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    heading = SECTION_HEADINGS[page_type]
    entry = f"- [[{slug}]] — {_clean_line(summary)}"

    heading_idx = lines.index(heading)
    end_idx = heading_idx + 1
    while end_idx < len(lines) and not lines[end_idx].startswith("## "):
        end_idx += 1

    section_entries = [line for line in lines[heading_idx + 1:end_idx] if line.strip()]
    section_entries = [line for line in section_entries if not line.startswith(f"- [[{slug}]]")]
    section_entries.append(entry)
    section_entries.sort(key=str.lower)

    new_lines = lines[:heading_idx + 1] + [""] + section_entries + lines[end_idx:]
    new_text = "\n".join(new_lines)

    total = len(re.findall(r"^- \[\[", new_text, re.MULTILINE))
    new_text = re.sub(r"Total pages: \d+", f"Total pages: {total}", new_text)
    index_path.write_text(new_text.rstrip("\n") + "\n", encoding="utf-8")


def append_log(
    action: str, subject: str, files: list[str], today: date, log_path: Path = LOG_PATH
) -> None:
    entry_lines = [f"## [{today.isoformat()}] {action} | {_clean_line(subject)}", ""]
    entry_lines += [f"- {f}" for f in files]
    entry_lines.append("")
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(entry_lines) + "\n")
