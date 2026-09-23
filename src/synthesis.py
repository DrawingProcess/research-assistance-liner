"""Phase 3 cross-paper synthesis (Search Agent scholar mode + Deep Research)
and curiosity-branch topic extraction, per design spec."""
from __future__ import annotations

import json
import re

from src import liner_client

NEXT_TOPICS_PATTERN = re.compile(r"NEXT_TOPICS:\s*(\[.*?\])", re.DOTALL)


def build_deep_research_prompt(topic: str) -> str:
    return (
        f'Research the current state of "{topic}", including common limitations '
        f"and open challenges across recent papers. End your report with exactly "
        f"one line in this format (a JSON array of up to 3 short topic strings): "
        f'NEXT_TOPICS: ["...", "...", "..."]'
    )


def parse_next_topics(report_text: str) -> list[str]:
    match = NEXT_TOPICS_PATTERN.search(report_text)
    if not match:
        return []
    try:
        topics = json.loads(match.group(1))
    except (ValueError, TypeError):
        return []
    if not isinstance(topics, list):
        return []
    return [t for t in topics if isinstance(t, str)]


def run_topic_synthesis(topic: str, *, deep_research: bool = False) -> dict:
    scholar_result = liner_client.search_agent(topic, mode="scholar")
    liner_client.raise_for_status(scholar_result, "search_agent (scholar synthesis)")
    if not deep_research:
        return {
            "search_agent_scholar": scholar_result["summary"],
            "deep_research": {"text": "", "references": [], "next_topics": []},
        }
    research_result = liner_client.deep_research(build_deep_research_prompt(topic))
    liner_client.raise_for_status(research_result, "deep_research")
    report_text = research_result["summary"]["text"]
    return {
        "search_agent_scholar": scholar_result["summary"],
        "deep_research": {
            "text": report_text,
            "references": research_result["summary"]["references"],
            "next_topics": parse_next_topics(report_text),
        },
    }
