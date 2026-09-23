"""Paper identity keys for v2 dedup: arXiv id, else normalized title.

Existing raw bodies stay immutable. New writes consult this module (and an
optional sidecar) before calling Liner extraction.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from src.backlog import slugify

IDENTITY_PATH = Path("research-gap/paper_identity.json")
_ARXIV_ID_RE = re.compile(r"(\d{4}\.\d{4,5})(?:v\d+)?")
_ZENODO_RE = re.compile(r"zenodo\.org/(?:records|doi)/(\d+)", re.I)


def canonical_id(url: str, title: str = "") -> str:
    lowered = (url or "").lower()
    if "arxiv.org/abs/" in lowered or "doi.org/10.48550/arxiv." in lowered:
        match = _ARXIV_ID_RE.search(url)
        if match:
            return f"arxiv:{match.group(1)}"
    zenodo = _ZENODO_RE.search(url or "")
    title_key = slugify(title) if title else ""
    if title_key:
        return f"title:{title_key}"
    if zenodo:
        return f"zenodo:{zenodo.group(1)}"
    return f"url:{(url or '').strip()}"


def load_index(path: Path = IDENTITY_PATH) -> dict:
    if not path.exists():
        return {"by_id": {}, "by_url": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_index(index: dict, path: Path = IDENTITY_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def register(cid: str, file_path: str, url: str, path: Path = IDENTITY_PATH) -> None:
    index = load_index(path)
    index.setdefault("by_id", {})[cid] = file_path
    if url:
        index.setdefault("by_url", {})[url] = file_path
    save_index(index, path)


def lookup_path(url: str, title: str = "", raw_dir: Path | None = None,
                identity_path: Path = IDENTITY_PATH) -> Path | None:
    cid = canonical_id(url, title)
    index = load_index(identity_path)
    stored = index.get("by_url", {}).get(url) or index.get("by_id", {}).get(cid)
    if stored:
        candidate = Path(stored)
        if candidate.exists():
            return candidate
    if raw_dir is None:
        return None
    from src.raw_paper import _canonical_url, _url_index
    existing = _url_index(raw_dir).get(_canonical_url(url))
    if existing is not None:
        return existing
    # Title-slug fallback is for Zenodo/open-web duplicates that share a
    # title but not a stable id. Two arXiv papers must stay distinct even
    # when a caller (or a test fixture) reuses the same title string.
    if cid.startswith("arxiv:"):
        return None
    if title:
        slug_path = raw_dir / f"{slugify(title)}.md"
        if slug_path.exists():
            return slug_path
    return None
