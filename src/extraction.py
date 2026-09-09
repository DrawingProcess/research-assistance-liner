"""Phase 3: per-paper structured extraction via Liner Search Agent.

Search Agent is used instead of a local Ollama model — see the design
spec's "Why this shape" section. Fields are requested as "|"-delimited
strings, not JSON arrays: Search Agent reliably emptied array-valued
fields (`{"problem":,...}`) when asked for `[...]` syntax, colliding with
how it handles inline citation markers like `[1]`, `[2]`.
"""
from __future__ import annotations

import json
import re

from src import liner_client

FIELDS = ["problem", "method", "dataset", "task", "evaluation", "limitations", "future_work"]
ITEM_SEPARATOR = " | "
SUMMARY_FIELD = "summary_ko"
MAX_SUMMARY_LENGTH = 150

# Backstop against extraction returning a full-sentence paraphrase or a
# placeholder non-answer instead of a short label — observed live (2026-08-04
# dry run) even with an improved prompt: e.g. a 379-character sentence as a
# "method" value, and "Not specified in abstract" turned into an entity page
# with 4 sources. These become canonical page titles/slugs downstream, where
# a one-off sentence can never be shared by another paper (defeating the
# point of a reusable concept) and a refusal string is outright wrong data.
MAX_ITEM_LENGTH = 100
_NON_ANSWER_RE = re.compile(
    r"^(not[\s-]?(specified|mentioned|provided|stated|applicable|available|reported|disclosed)"
    r"|n/?a|none( (provided|mentioned|specified|reported))?|unknown|tbd|n/?d)\b",
    re.IGNORECASE,
)

PROMPT_TEMPLATE = """Given this paper, respond with ONLY a JSON object (no prose, no markdown fences). Do NOT use square brackets anywhere in your answer.

Each of these keys must map to a single string value, with multiple items separated by " | " (or an empty string if none): problem, method, dataset, task, evaluation, limitations, future_work.

Each item must be a SHORT name or noun phrase, at most 6 words — the kind of label you'd use as a heading or tag, never a full sentence or explanation. Good examples: "ScanNet", "3D Gaussian Splatting", "semantic segmentation", "mIoU", "requires ground-truth camera poses". Bad: a sentence describing what the method does or why it matters.

If the abstract does not give a value for a field, use an empty string for that field. Never write a phrase like "not specified" or "not mentioned" as if it were a real value.

Also include a "summary_ko" key: ONE natural Korean sentence (not a list, no " | " separators, at most 80 characters) summarizing this paper's problem and method in plain Korean for a Korean-speaking researcher — not a translation of the English labels above, a genuine one-line summary.

Title: {title}
Abstract: {abstract}"""


def build_extraction_prompt(title: str, abstract: str) -> str:
    return PROMPT_TEMPLATE.format(title=title, abstract=abstract)


def _split_items(value: str) -> list[str]:
    items = [item.strip() for item in value.split(ITEM_SEPARATOR) if item.strip()]
    return [
        item for item in items
        if len(item) <= MAX_ITEM_LENGTH and not _NON_ANSWER_RE.match(item)
    ]


def _clean_summary(value: str) -> str:
    value = value.strip()
    if len(value) > MAX_SUMMARY_LENGTH:
        value = value[:MAX_SUMMARY_LENGTH].rstrip() + "..."
    return value


def parse_extraction_response(text: str) -> dict | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or not all(field in data for field in FIELDS):
        return None
    if not all(isinstance(data[field], str) for field in FIELDS):
        return None
    result = {field: _split_items(data[field]) for field in FIELDS}
    summary = data.get(SUMMARY_FIELD)
    result[SUMMARY_FIELD] = _clean_summary(summary) if isinstance(summary, str) and summary.strip() else ""
    return result


def extract_paper(paper: dict) -> dict | None:
    prompt = build_extraction_prompt(paper["title"], paper.get("description", ""))
    result = liner_client.search_agent(prompt, mode="general")
    liner_client.raise_for_status(result, "search_agent (extraction)")
    return parse_extraction_response(result["summary"]["text"])
