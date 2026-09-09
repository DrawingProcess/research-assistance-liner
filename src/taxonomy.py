"""Per-topic paper taxonomy synthesis — classifies a topic's captured
papers along their core methodological axis, once enough papers exist to
make classification meaningful. Piloted manually (2026-08-08, semantic
3DGS) before being automated here; see queries/semantic-3dgs-feature-
lifting-taxonomy.md for the reference example this format is based on.

Runs once per topic (topics are only ever processed once — see
daily_pipeline.process_topic), as part of the same run that captures the
topic's papers, using the already-extracted problem/method labels (no
extra reading of raw text, one Search Agent call).

Every title the model returns is checked against the caller's own known
paper titles before use — a hallucinated or paraphrased title is dropped,
never trusted to resolve a source path or count as a real classification.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from src.backlog import slugify
from src.canonical_pages import _format_frontmatter
from src import liner_client
from src import wiki_index

MIN_PAPERS_FOR_TAXONOMY = 5
TAXONOMY_DIR = Path("queries")
MAX_RELATED_LINKS = 5

PROMPT_TEMPLATE = """You are analyzing {count} research papers captured under the topic "{topic}". Each paper is given with its title and short extracted problem/method labels (not full text, not the abstract).

Identify ONE core technical question that most of these papers are actually answering — the main axis along which their approaches genuinely differ — and classify each paper into 2 to 6 clusters along that axis based on its distinct strategy. If a paper doesn't meaningfully address that core question (e.g. it solves a different problem, or is off-topic despite matching the search), put it in "off_axis" with a short reason instead of forcing it into a cluster. If you can identify a real, specific gap — an obvious combination of two cluster strategies that no paper here attempts — describe it in one short paragraph as "insight"; otherwise use an empty string for "insight".

Use each paper's title EXACTLY as given below, character for character — do not paraphrase, translate, or abbreviate it. Do not invent a paper that isn't in the list below. Do NOT use square brackets anywhere except where the JSON shape below requires them.

Respond with ONLY a JSON object (no prose, no markdown fences) in exactly this shape:
{{"axis": "...", "clusters": [{{"name": "...", "description": "...", "papers": ["<exact title>", "..."]}}], "off_axis": [{{"title": "<exact title>", "reason": "..."}}], "insight": "..."}}

Papers:
{papers_block}"""


def build_taxonomy_prompt(topic: str, papers: list[dict]) -> str:
    lines = []
    for i, p in enumerate(papers, 1):
        problem = " | ".join(p.get("problem") or [])
        method = " | ".join(p.get("method") or [])
        lines.append(f"{i}. Title: {p['title']}\n   Problem: {problem}\n   Method: {method}")
    return PROMPT_TEMPLATE.format(topic=topic, count=len(papers), papers_block="\n".join(lines))


def parse_taxonomy_response(text: str, known_titles: set[str]) -> dict | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None

    axis = data.get("axis")
    if not isinstance(axis, str) or not axis.strip():
        return None

    raw_clusters = data.get("clusters")
    if not isinstance(raw_clusters, list):
        return None
    clusters = []
    for c in raw_clusters:
        if not isinstance(c, dict):
            continue
        name = c.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        description = c.get("description")
        description = description.strip() if isinstance(description, str) else ""
        raw_papers = c.get("papers")
        papers = [p for p in raw_papers if isinstance(p, str) and p in known_titles] if isinstance(raw_papers, list) else []
        if not papers:
            continue  # a cluster with no recognizable real paper is useless
        clusters.append({"name": name.strip(), "description": description, "papers": papers})
    if len(clusters) < 2:
        return None

    # A paper the model already placed in a cluster must not also appear in
    # off_axis (observed live: the model sometimes hedges by listing the
    # same paper both ways) — the cluster placement wins, since a reader
    # seeing the same title twice with a contradicting label is confusing.
    clustered_titles = {p for c in clusters for p in c["papers"]}
    off_axis = []
    raw_off_axis = data.get("off_axis")
    if isinstance(raw_off_axis, list):
        for o in raw_off_axis:
            if not isinstance(o, dict):
                continue
            title = o.get("title")
            if not isinstance(title, str) or title not in known_titles or title in clustered_titles:
                continue
            reason = o.get("reason")
            off_axis.append({"title": title, "reason": reason.strip() if isinstance(reason, str) else ""})

    insight = data.get("insight")
    insight = insight.strip() if isinstance(insight, str) else ""

    return {"axis": axis.strip(), "clusters": clusters, "off_axis": off_axis, "insight": insight}


# A topic is only ever processed once (see daily_pipeline.process_topic),
# so a parse failure here means no second chance later — worth one retry.
# Observed live: the model's large structured JSON (5-7 clusters across up
# to 20 papers in one response) sometimes comes back malformed even though
# the same prompt succeeds on a fresh call; retrying is cheap ($0.02/call).
MAX_ATTEMPTS = 2


def generate_taxonomy(topic: str, papers: list[dict]) -> dict | None:
    known_titles = {p["title"] for p in papers}
    prompt = build_taxonomy_prompt(topic, papers)
    for attempt in range(MAX_ATTEMPTS):
        result = liner_client.search_agent(prompt, mode="general")
        liner_client.raise_for_status(result, "search_agent (taxonomy)")
        parsed = parse_taxonomy_response(result["summary"]["text"], known_titles)
        if parsed is not None:
            return parsed
    return None


def _render_body(title: str, axis: str, taxonomy: dict, related_slugs: list[str]) -> str:
    lines = [f"# {title}", "", axis, ""]
    for c in taxonomy["clusters"]:
        lines += [f"## {c['name']}", "", c["description"], ""]
        lines += [f"- {p}" for p in c["papers"]]
        lines.append("")
    if taxonomy["off_axis"]:
        lines += ["## Off-axis", ""]
        lines += [f"- {o['title']} — {o['reason']}" if o["reason"] else f"- {o['title']}" for o in taxonomy["off_axis"]]
        lines.append("")
    if taxonomy["insight"]:
        lines += ["## Insight", "", taxonomy["insight"], ""]
    lines += ["## Related", ""]
    lines += [f"- [[{slug}]]" for slug in related_slugs]
    return "\n".join(lines) + "\n"


def write_taxonomy_page(
    topic: str, taxonomy: dict, sources_by_title: dict[str, str],
    related_slugs: list[str], today: date,
) -> Path | None:
    title = f"{topic}: paper taxonomy"
    path = TAXONOMY_DIR / f"{slugify(title)}.md"
    if path.exists():
        return None  # topics are only ever processed once; a pre-existing file means don't overwrite

    referenced_titles = [p for c in taxonomy["clusters"] for p in c["papers"]] + [o["title"] for o in taxonomy["off_axis"]]
    sources = sorted({sources_by_title[t] for t in referenced_titles if t in sources_by_title})

    fm = {
        "title": title, "created": today.isoformat(), "updated": today.isoformat(),
        "type": "query", "tags": ["research"], "sources": sources,
        "confidence": "medium", "contested": False, "contradictions": [],
    }
    body = _render_body(title, taxonomy["axis"], taxonomy, related_slugs)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_format_frontmatter(fm) + "\n" + body, encoding="utf-8")

    slug = slugify(title)
    summary = f"Auto-generated taxonomy: {taxonomy['axis']}"
    wiki_index.upsert_index_entry("query", slug, title, summary)
    wiki_index.append_log("create", title, [str(path)], today)
    return path
