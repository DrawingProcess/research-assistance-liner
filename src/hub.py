"""Topic hub pages: the v2 sink for synthesis, papers, themes, and adjacent topics."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from src.backlog import slugify
from src.canonical_pages import _format_frontmatter, create_or_update_page, parse_frontmatter, read_page
from src.wiki_index import append_log, upsert_index_entry

SECTION_ORDER = [
    "Definition", "Open challenges", "Papers", "Themes", "Adjacent", "Related",
]


def _clean(text: str) -> str:
    return " ".join(text.split())


def _split_sections(body: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {name: [] for name in SECTION_ORDER}
    current = None
    preamble: list[str] = []
    for line in body.splitlines():
        if line.startswith("# "):
            continue
        heading = line[3:].strip() if line.startswith("## ") else None
        if heading in SECTION_ORDER:
            current = heading
            continue
        if current is None:
            if line.strip():
                preamble.append(line)
            continue
        sections[current].append(line)
    if preamble and not any(x.strip() for x in sections["Definition"]):
        sections["Definition"] = preamble
    return sections


def _emit(title: str, sections: dict[str, list[str]]) -> str:
    lines = [f"# {_clean(title)}", ""]
    for name in SECTION_ORDER:
        lines += [f"## {name}", ""]
        content = [ln for ln in sections.get(name, []) if ln.strip() != ""]
        if content:
            lines += content
            if content[-1] != "":
                lines.append("")
        else:
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def ensure_hub(topic: str, today: date) -> None:
    if read_page("concept", topic) is None:
        create_or_update_page(
            "concept", topic, today, source_path="",
            wikilinks=[], summary=f"Research hub for the topic {topic!r}.",
        )


def update_hub(
    topic: str, today: date, *,
    sources: list[str],
    definition: str = "",
    challenges: list[str] | None = None,
    papers: list[dict] | None = None,
    themes: dict[str, list[str]] | None = None,
    adjacent: list[str] | None = None,
    related: list[str] | None = None,
) -> None:
    ensure_hub(topic, today)
    existing = read_page("concept", topic)
    assert existing is not None
    fm, body = existing
    for s in sources:
        if s and s not in fm.get("sources", []):
            fm.setdefault("sources", []).append(s)
    if len(fm.get("sources") or []) >= 2:
        fm["confidence"] = "high"
    fm["updated"] = today.isoformat()
    fm["tags"] = ["research", "research-gap"]

    sections = _split_sections(body)
    if definition.strip() and not any(x.strip() for x in sections["Definition"]):
        sections["Definition"] = [definition.strip(), ""]
    for item in challenges or []:
        bullet = f"- {_clean(item)}"
        if bullet not in sections["Open challenges"]:
            sections["Open challenges"].append(bullet)
    for paper in papers or []:
        path = paper.get("path") or ""
        title = _clean(paper.get("title") or path)
        url = paper.get("url") or ""
        bullet = f"- {title} — `{path}`" + (f" ({url})" if url else "")
        if path and not any(path in ln for ln in sections["Papers"]):
            sections["Papers"].append(bullet)
    for label, paths in sorted((themes or {}).items()):
        unique_paths = list(dict.fromkeys(paths))
        bullet = f"- {_clean(label)} ({len(unique_paths)}) — " + ", ".join(f"`{p}`" for p in unique_paths)
        prefix = f"- {_clean(label)} ("
        sections["Themes"] = [ln for ln in sections["Themes"] if not ln.startswith(prefix)]
        sections["Themes"].append(bullet)
    for topic_name in adjacent or []:
        bullet = f"- {_clean(topic_name)}"
        if bullet not in sections["Adjacent"]:
            sections["Adjacent"].append(bullet)
    for slug in related or []:
        link = f"- [[{slug}]]"
        if link not in sections["Related"]:
            sections["Related"].append(link)

    path = Path("concepts") / f"{slugify(topic)}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_format_frontmatter(fm) + "\n" + _emit(fm.get("title", topic), sections), encoding="utf-8")
    upsert_index_entry("concept", slugify(topic), fm.get("title", topic),
                       f"Research hub for the topic {topic!r}.")
    append_log("update", fm.get("title", topic), [str(path)], today)
