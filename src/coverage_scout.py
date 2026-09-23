"""Weekly coverage scout: find fields missing from done hubs, without
enqueueing them. A person picks from Discord / coverage_candidates.json
and adds backlog entries with source: coverage-gap.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from src import liner_client
from src.synthesis import parse_next_topics

CANDIDATES_PATH = Path("research-gap/coverage_candidates.json")
SCOUT_WEEKDAYS = {0}  # Monday
MAX_CANDIDATES = 8


def covered_topics(backlog: dict) -> list[str]:
    return [t["topic"] for t in backlog.get("topics", []) if t.get("status") == "done"]


def build_scout_prompt(topics: list[str]) -> str:
    listing = ", ".join(topics[:80]) or "(none yet)"
    return (
        f"The following research topics are already covered in a personal wiki: {listing}. "
        "List up to 8 adjacent or orthogonal research fields that are missing from this set "
        "and would be independent areas, not synonyms of the listed topics. "
        'End your report with exactly one line: NEXT_TOPICS: ["...", "..."]'
    )


def scout_coverage(backlog: dict, today: date, path: Path = CANDIDATES_PATH) -> dict:
    topics = covered_topics(backlog)
    if not topics:
        payload = {"date": today.isoformat(), "candidates": []}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    result = liner_client.deep_research(build_scout_prompt(topics))
    liner_client.raise_for_status(result, "deep_research (coverage scout)")
    text = result["summary"]["text"]
    names = parse_next_topics(text)[:MAX_CANDIDATES]
    candidates = []
    for name in names:
        web = liner_client.search_web(name, max_results=5)
        liner_client.raise_for_status(web, f"search_web for {name!r}")
        qa = liner_client.quick_answer(
            f'Is "{name}" an independent research field rather than a synonym of an existing topic? '
            "Answer yes or no and one sentence."
        )
        liner_client.raise_for_status(qa, f"quick_answer for {name!r}")
        hits = web.get("response", {}).get("results") or []
        candidates.append({
            "topic": name,
            "web_hits": len(hits),
            "web_titles": [h.get("title") or "" for h in hits[:3]],
            "independent": qa.get("summary", {}).get("text") or "",
            "source": "coverage-gap",
        })
    payload = {"date": today.isoformat(), "covered": topics, "candidates": candidates, "report": text}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def format_scout_message(payload: dict) -> str:
    candidates = payload.get("candidates") or []
    lines = [f"[Coverage scout] {payload.get('date', '')} — {len(candidates)} candidates", ""]
    if not candidates:
        lines.append("No missing-field candidates this week.")
        return "\n".join(lines)
    lines.append("고르면 backlog에 source: coverage-gap 으로 넣으세요. 자동 추가는 하지 않습니다.")
    lines.append("")
    for c in candidates:
        lines.append(f"- {c['topic']} (web {c.get('web_hits', 0)})")
        if c.get("independent"):
            lines.append(f"  {c['independent'][:240]}")
    return "\n".join(lines)


def scout_and_notify(today: date, send, backlog: dict) -> dict:
    payload = scout_coverage(backlog, today)
    if payload.get("candidates"):
        send(format_scout_message(payload))
    return payload
