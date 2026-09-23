# src/canonical_pages.py
"""Creates and updates canonical entities/concepts/comparisons pages per
SCHEMA.md's rules: sources provenance, confidence, wikilinks, and
simultaneous index.md/log.md sync (see src/wiki_index.py).

Frontmatter is a small hand-rolled format, not general YAML: string
scalars are always JSON-encoded (`key: "value"`, escaping embedded quotes
and newlines), booleans are bare `true`/`false`, and lists are
JSON-flow-array `key: [...]` (valid YAML, parseable with json.loads).
This project writes and reads its own frontmatter, so this is sufficient
without a YAML dependency — but it means hand-edited block-style YAML is
NOT supported, and parse_frontmatter raises loudly rather than silently
mis-parsing it (Final review, Finding I5).
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from src.backlog import slugify
from src.wiki_index import append_log, upsert_index_entry

CANONICAL_DIRS = {
    "entity": Path("entities"), "concept": Path("concepts"), "comparison": Path("comparisons"),
}


def page_path(page_type: str, title: str) -> Path:
    return CANONICAL_DIRS[page_type] / f"{slugify(title)}.md"


def _clean_line(text: str) -> str:
    """Collapse embedded newlines/control chars so external text is always
    safe as a single markdown line (heading, bullet, index/log entry) —
    without this, a label containing e.g. '\\n## Injected' can permanently
    corrupt index.md's section structure or a page's body (Final review,
    Finding C2)."""
    return " ".join(text.split())


def parse_frontmatter(text: str) -> tuple[dict, str]:
    end = text.index("\n---\n", 4)
    fm_text = text[4:end]
    body = text[end + 5:]
    fm: dict = {}
    for line in fm_text.splitlines():
        if not line.strip() or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if value.startswith("["):
            fm[key] = json.loads(value)
        elif value.startswith('"'):
            # json.loads (not a naive [1:-1] slice) so this exactly reverses
            # _format_frontmatter's json.dumps, including embedded quotes,
            # backslashes and escaped newlines (Finding C2).
            fm[key] = json.loads(value)
        elif value in ("true", "false"):
            fm[key] = value == "true"
        else:
            fm[key] = value

    # This parser only understands JSON-flow lists. Block-style YAML
    # (`tags:\n  - research`) parses to an empty string here, and writing
    # that back would silently destroy the research-gap tag and drop the
    # page out of gap detection forever. Fail loudly instead (Finding I5).
    for list_field in ("tags", "sources", "contradictions"):
        if list_field in fm and not isinstance(fm[list_field], list):
            raise ValueError(
                f"{list_field!r} in this page's frontmatter is not a JSON-flow "
                f"list (got {fm[list_field]!r}) — likely hand-edited in "
                "block-style YAML, which this project's hand-rolled parser "
                "doesn't support. Convert it to `key: [...]` flow-list syntax."
            )
    if "contested" in fm and not isinstance(fm["contested"], bool):
        raise ValueError(f"'contested' in this page's frontmatter is not true/false (got {fm['contested']!r})")
    return fm, body


def _format_frontmatter(fm: dict) -> str:
    lines = ["---"]
    for key, value in fm.items():
        if isinstance(value, list):
            lines.append(f"{key}: {json.dumps(value)}")
        elif isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        elif isinstance(value, str):
            # Always json.dumps every string scalar: it escapes embedded
            # quotes AND control characters (a newline becomes the two-char
            # escape \n, never a literal line break), so external text can
            # never break out of its frontmatter field (Finding C2).
            lines.append(f"{key}: {json.dumps(value)}")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines)


def read_page(page_type: str, title: str) -> tuple[dict, str] | None:
    path = page_path(page_type, title)
    if not path.exists():
        return None
    return parse_frontmatter(path.read_text(encoding="utf-8"))


def _render_body(title: str, wikilinks: list[str], body_section: tuple[str, str] | None) -> str:
    lines = [f"# {_clean_line(title)}", ""]
    if body_section:
        heading, bullet = body_section
        lines += [f"## {heading}", "", f"- {_clean_line(bullet)}", ""]
    lines += ["## Related", ""]
    # dict.fromkeys dedupes while preserving order: a caller can legitimately
    # pass the same slug twice (e.g. an extracted label identical to the
    # topic itself makes hub_slug appear among the sibling slugs), and
    # _merge_body already dedupes on the update path (re-review, Minor 1).
    lines += [f"- [[{link}]]" for link in dict.fromkeys(wikilinks)]
    return "\n".join(lines) + "\n"


def _merge_body(body: str, wikilinks: list[str], body_section: tuple[str, str] | None) -> str:
    lines = body.splitlines()
    if body_section:
        heading, bullet = body_section
        heading_line, bullet_line = f"## {heading}", f"- {_clean_line(bullet)}"
        if heading_line in lines:
            if bullet_line not in lines:
                idx = lines.index(heading_line)
                lines.insert(idx + 2, bullet_line)
        else:
            lines += ["", heading_line, "", bullet_line]
    for link in wikilinks:
        link_line = f"- [[{link}]]"
        if link_line not in lines:
            if "## Related" not in lines:
                lines += ["", "## Related", ""]
            lines.append(link_line)
    return "\n".join(lines) + "\n"


MIN_SOURCES_TO_CREATE = 2


def stage_or_write_page(
    page_type: str, title: str, today: date, source_path: str | list[str],
    wikilinks: list[str], summary: str, pending_sources: list[str] | None = None,
    body_section: tuple[str, str] | None = None,
) -> str:
    """Create a canonical page only when it already exists or combined
    evidence has reached MIN_SOURCES_TO_CREATE. Otherwise return 'staged'."""
    new_sources = [source_path] if isinstance(source_path, str) else list(source_path)
    new_sources = list(dict.fromkeys(s for s in new_sources if s))
    existing = read_page(page_type, title)
    if existing is None:
        combined = list(dict.fromkeys(list(pending_sources or []) + new_sources))
        if len(combined) < MIN_SOURCES_TO_CREATE:
            return "staged"
        return create_or_update_page(
            page_type, title, today, combined, wikilinks, summary, body_section=body_section,
        )
    return create_or_update_page(
        page_type, title, today, new_sources, wikilinks, summary, body_section=body_section,
    )


def create_or_update_page(
    page_type: str, title: str, today: date, source_path: str | list[str],
    wikilinks: list[str], summary: str, body_section: tuple[str, str] | None = None,
) -> str:
    # A single string is still accepted (every existing caller passes one),
    # but a caller with several sources for the same creation — e.g. a gap
    # candidate whose whole evidence base is known up front — no longer has
    # to call this once per source just to accumulate them (wasteful: N
    # file rewrites, N index.md updates, N near-identical log.md entries
    # for what's really one creation event). Falsy entries are dropped so
    # source_path="" (the hub-page case) still yields sources=[].
    new_sources = [source_path] if isinstance(source_path, str) else list(source_path)
    new_sources = list(dict.fromkeys(s for s in new_sources if s))

    existing = read_page(page_type, title)
    if existing is None:
        fm = {
            "title": title, "created": today.isoformat(), "updated": today.isoformat(),
            "type": page_type, "tags": ["research", "research-gap"],
            "sources": new_sources,
            # Previously always "medium" on creation, since source_path was
            # always exactly one source — now a multi-source creation (e.g.
            # a gap candidate created with its full evidence in one call)
            # must be able to start at "high" too, not wait for a later
            # update that, for auto-created pages like comparisons/, never
            # actually comes (they're only ever created once).
            "confidence": "high" if len(new_sources) >= 2 else "medium",
            "contested": False, "contradictions": [],
        }
        body = _render_body(title, wikilinks, body_section)
        action = "create"
    else:
        fm, body = existing
        sources = fm.get("sources", [])
        for s in new_sources:
            if s not in sources:
                sources.append(s)
        fm["sources"] = sources
        if len(sources) >= 2:
            fm["confidence"] = "high"
        fm["updated"] = today.isoformat()
        body = _merge_body(body, wikilinks, body_section)
        action = "update"

    path = page_path(page_type, title)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_format_frontmatter(fm) + "\n" + body, encoding="utf-8")

    slug = slugify(title)
    upsert_index_entry(page_type, slug, title, summary)
    append_log(action, title, [str(path)], today)
    return action
