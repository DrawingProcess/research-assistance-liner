"""Thin client for the Liner APIs used by the research-gap pipeline.

Reads LINER_API_KEY from the process environment. Copy .env.example to .env
and load it with your preferred local environment tool before running the pipeline.
"""
from __future__ import annotations

import json
import re
import os
from typing import Any

import requests

BASE_URL = "https://platform.liner.com"
# Status codes where the failure is about the account/request as a whole,
# not the specific paper or topic being processed — invalid/expired key
# (401), out of credits (402), rate-limited (429). Every subsequent call
# this run will fail identically, so retrying a different paper or topic
# is pointless and just burns wall-clock time on calls guaranteed to fail.
ACCOUNT_LEVEL_STATUS_CODES = {401, 402, 429}


class AccountLevelAPIError(RuntimeError):
    """Raised instead of a plain RuntimeError when the status code is one
    of ACCOUNT_LEVEL_STATUS_CODES — callers use this to distinguish "stop
    trying more papers/topics this run" from "this one paper/call had a
    transient or content-specific problem, move on to the next one"."""


def raise_for_status(result: dict[str, Any], context: str) -> None:
    status = result["status_code"]
    if status < 400:
        return
    error_cls = AccountLevelAPIError if status in ACCOUNT_LEVEL_STATUS_CODES else RuntimeError
    raise error_cls(f"{context} failed with status {status}")


def _api_key() -> str:
    key = os.environ.get("LINER_API_KEY", "").strip()
    if not key:
        raise RuntimeError("LINER_API_KEY is not set in the environment")
    return key


def _headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {"x-api-key": _api_key(), "Content-Type": "application/json"}
    if extra:
        headers.update(extra)
    return headers


def _post_json(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    resp = requests.post(f"{BASE_URL}{path}", headers=_headers(), json=payload, timeout=60)
    try:
        body = resp.json()
    except ValueError:
        body = {"_raw_text": resp.text}
    return {"status_code": resp.status_code, "response": body}


def _parse_sse_events(lines) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for raw in lines:
        if not raw or not raw.startswith("data:"):
            continue
        payload = raw[len("data:"):].strip()
        if payload == "[DONE]":
            continue
        try:
            events.append(json.loads(payload))
        except json.JSONDecodeError:
            continue
    return events


def _summarize_sse(events: list[dict[str, Any]]) -> dict[str, Any]:
    text = "".join(e.get("delta", "") for e in events if e.get("type") == "text-delta")
    references: list[Any] = []
    for e in events:
        if e.get("type") == "data-search-references":
            references.extend(e.get("data", {}).get("references", []))
    return {"text": text, "references": references}


def _post_sse(path: str, payload: dict[str, Any], extra_headers: dict[str, str] | None = None) -> dict[str, Any]:
    with requests.post(
        f"{BASE_URL}{path}", headers=_headers(extra_headers), json=payload, stream=True, timeout=180
    ) as resp:
        status_code = resp.status_code
        raw_lines = [line if line is not None else "" for line in resp.iter_lines(decode_unicode=True)]
    return {"status_code": status_code, "summary": _summarize_sse(_parse_sse_events(raw_lines))}


def search_scholar(query: str, max_results: int = 20) -> dict[str, Any]:
    return _post_json("/api/v1/tools/search/scholar", {"query": query, "max_results": max_results})


def search_agent(query: str, mode: str = "general") -> dict[str, Any]:
    payload = {"messages": [{"role": "user", "content": query}], "mode": mode}
    return _post_sse("/api/v1/agents/search", payload)


def deep_research(query: str) -> dict[str, Any]:
    payload = {"messages": [{"role": "user", "content": query}]}
    return _post_sse("/api/v1/agents/deep-research", payload, extra_headers={"Accept": "text/event-stream"})
